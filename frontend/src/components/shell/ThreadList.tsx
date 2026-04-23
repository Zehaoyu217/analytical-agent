/**
 * ThreadList — secondary column listing conversations grouped by recency.
 *
 * Sections (each hidden when empty):
 *   - Pinned (pinned and not frozen)
 *   - Today / This week / Older (active conversations)
 *   - Checkpoints (frozen conversations, sorted by frozenAt desc)
 *
 * Row affordances: title-only filter input at top, per-row MoreMenu
 * (Pin/Unpin, Freeze, Rename, Duplicate, Delete, Export). Pin and frozen
 * state are persisted on the backend via the store actions.
 */

import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
  type MouseEvent,
} from "react";
import {
  ChevronLeft,
  Lock,
  MoreHorizontal,
  Pin,
  Plus,
  Trash2,
} from "lucide-react";
import { useChatStore, type Conversation } from "@/lib/store";
import { extractTextContent } from "@/lib/utils";
import {
  useUiStore,
  THREAD_W_MIN,
  THREAD_W_MAX,
  selectThreadW,
} from "@/lib/ui-store";
import { cn } from "@/lib/utils";
import { Resizer } from "./Resizer";

interface ThreadSection {
  id: "pinned" | "today" | "week" | "older" | "checkpoints";
  label: string;
  items: Conversation[];
}

const MS_PER_DAY = 24 * 60 * 60 * 1000;
const WEEK_MS = 7 * MS_PER_DAY;

function startOfDay(ts: number): number {
  const d = new Date(ts);
  d.setHours(0, 0, 0, 0);
  return d.getTime();
}

function relativeTime(ts: number, now: number): string {
  const diff = now - ts;
  if (diff < 60_000) return "now";
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m`;
  if (diff < MS_PER_DAY) return `${Math.floor(diff / 3_600_000)}h`;
  if (diff < 2 * MS_PER_DAY) return "yest";
  if (diff < WEEK_MS) return `${Math.floor(diff / MS_PER_DAY)}d`;
  if (diff < 4 * WEEK_MS) return `${Math.floor(diff / WEEK_MS)}w`;
  return new Date(ts).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

function isFrozen(c: Conversation): boolean {
  return typeof c.frozenAt === "number" && c.frozenAt > 0;
}

function groupConversations(
  conversations: Conversation[],
  now: number,
): ThreadSection[] {
  const sod = startOfDay(now);
  const weekCut = sod - 6 * MS_PER_DAY;

  const buckets: Record<ThreadSection["id"], Conversation[]> = {
    pinned: [],
    today: [],
    week: [],
    older: [],
    checkpoints: [],
  };

  for (const c of conversations) {
    if (isFrozen(c)) {
      buckets.checkpoints.push(c);
      continue;
    }
    if (c.pinned) {
      buckets.pinned.push(c);
      continue;
    }
    const t = c.updatedAt;
    if (t >= sod) buckets.today.push(c);
    else if (t >= weekCut) buckets.week.push(c);
    else buckets.older.push(c);
  }

  const sortDesc = (a: Conversation, b: Conversation): number =>
    b.updatedAt - a.updatedAt;
  const sortFrozenDesc = (a: Conversation, b: Conversation): number =>
    (b.frozenAt ?? 0) - (a.frozenAt ?? 0);

  buckets.pinned.sort(sortDesc);
  buckets.today.sort(sortDesc);
  buckets.week.sort(sortDesc);
  buckets.older.sort(sortDesc);
  buckets.checkpoints.sort(sortFrozenDesc);

  return [
    { id: "pinned", label: "Pinned", items: buckets.pinned },
    { id: "today", label: "Today", items: buckets.today },
    { id: "week", label: "This week", items: buckets.week },
    { id: "older", label: "Older", items: buckets.older },
    { id: "checkpoints", label: "Checkpoints", items: buckets.checkpoints },
  ];
}

function previewOf(conv: Conversation): string {
  const last = conv.messages[conv.messages.length - 1];
  if (!last) return "no messages yet";
  const text = extractTextContent(last.content).trim().replace(/\s+/g, " ");
  return text.length > 0 ? text : `${last.role} · ${last.status}`;
}

interface MoreMenuProps {
  conversation: Conversation;
  onClose: () => void;
}

function MoreMenu({ conversation, onClose }: MoreMenuProps) {
  const setPinned = useChatStore((s) => s.setConversationPinned);
  const freeze = useChatStore((s) => s.freezeConversation);
  const rename = useChatStore((s) => s.renameConversation);
  const duplicate = useChatStore((s) => s.duplicateConversation);
  const remove = useChatStore((s) => s.deleteConversationRemote);

  const frozen = isFrozen(conversation);

  function safe(fn: () => Promise<unknown>): void {
    fn()
      .catch((err: unknown) => {
        // eslint-disable-next-line no-console
        console.error("ThreadList action failed", err);
      })
      .finally(onClose);
  }

  return (
    <div
      role="menu"
      className={cn(
        "absolute right-2 top-7 z-20 min-w-[140px] rounded border border-line-2",
        "bg-bg-1 shadow-lg py-1 text-[12px]",
      )}
      onClick={(e) => e.stopPropagation()}
    >
      <button
        type="button"
        role="menuitem"
        className="block w-full px-3 py-1 text-left hover:bg-bg-2"
        onClick={() => safe(() => setPinned(conversation.id, !conversation.pinned))}
        disabled={frozen}
      >
        {conversation.pinned ? "Unpin" : "Pin"}
      </button>
      {!frozen && (
        <button
          type="button"
          role="menuitem"
          className="block w-full px-3 py-1 text-left hover:bg-bg-2"
          onClick={() => {
            const ok = window.confirm(
              "Freeze this conversation? You won't be able to add new turns. To continue, duplicate it.",
            );
            if (!ok) {
              onClose();
              return;
            }
            safe(() => freeze(conversation.id));
          }}
        >
          Freeze
        </button>
      )}
      <button
        type="button"
        role="menuitem"
        className="block w-full px-3 py-1 text-left hover:bg-bg-2"
        onClick={() => {
          const next = window.prompt("Rename conversation", conversation.title);
          if (!next || next === conversation.title) {
            onClose();
            return;
          }
          safe(() => rename(conversation.id, next));
        }}
      >
        Rename
      </button>
      <button
        type="button"
        role="menuitem"
        className="block w-full px-3 py-1 text-left hover:bg-bg-2"
        onClick={() => safe(() => duplicate(conversation.id))}
      >
        Duplicate
      </button>
      <button
        type="button"
        role="menuitem"
        className="block w-full px-3 py-1 text-left hover:bg-bg-2"
        onClick={() => {
          const blob = new Blob([JSON.stringify(conversation, null, 2)], {
            type: "application/json",
          });
          const url = URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = url;
          a.download = `${conversation.title || conversation.id}.json`;
          a.click();
          URL.revokeObjectURL(url);
          onClose();
        }}
      >
        Export
      </button>
      <button
        type="button"
        role="menuitem"
        className="block w-full px-3 py-1 text-left text-danger hover:bg-bg-2"
        onClick={() => {
          const ok = window.confirm(`Delete "${conversation.title}"?`);
          if (!ok) {
            onClose();
            return;
          }
          safe(() => remove(conversation.id));
        }}
      >
        Delete
      </button>
    </div>
  );
}

type SweepOption =
  | { kind: "all" }
  | { kind: "older"; days: number; label: string };

const SWEEP_OPTIONS: SweepOption[] = [
  { kind: "all" },
  { kind: "older", days: 7, label: "7 days" },
  { kind: "older", days: 30, label: "30 days" },
  { kind: "older", days: 90, label: "90 days" },
];

export function ThreadList() {
  const conversations = useChatStore((s) => s.conversations);
  const activeId = useChatStore((s) => s.activeConversationId);
  const setActive = useChatStore((s) => s.setActiveConversation);
  const createLocal = useChatStore((s) => s.createConversation);
  const createRemote = useChatStore((s) => s.createConversationRemote);
  const bulkDelete = useChatStore((s) => s.bulkDeleteConversations);

  const threadW = useUiStore(selectThreadW);
  const setThreadW = useUiStore((s) => s.setThreadW);
  const toggleThreads = useUiStore((s) => s.toggleThreads);

  const [filter, setFilter] = useState("");
  const [creating, setCreating] = useState(false);
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);
  const [sweepOpen, setSweepOpen] = useState(false);

  const menuContainerRef = useRef<HTMLDivElement | null>(null);
  const sweepContainerRef = useRef<HTMLDivElement | null>(null);

  // Close the menu on outside click.
  useEffect(() => {
    if (!openMenuId) return;
    function onDocClick(ev: globalThis.MouseEvent) {
      if (
        menuContainerRef.current &&
        !menuContainerRef.current.contains(ev.target as Node)
      ) {
        setOpenMenuId(null);
      }
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [openMenuId]);

  // Close the sweep menu on outside click / Escape.
  useEffect(() => {
    if (!sweepOpen) return;
    function onDocClick(ev: globalThis.MouseEvent) {
      if (
        sweepContainerRef.current &&
        !sweepContainerRef.current.contains(ev.target as Node)
      ) {
        setSweepOpen(false);
      }
    }
    function onKey(ev: globalThis.KeyboardEvent) {
      if (ev.key === "Escape") setSweepOpen(false);
    }
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [sweepOpen]);

  const filtered = useMemo(() => {
    const q = filter.trim().toLowerCase();
    if (!q) return conversations;
    return conversations.filter((c) => c.title.toLowerCase().includes(q));
  }, [conversations, filter]);

  const sections = useMemo(
    () => groupConversations(filtered, Date.now()),
    [filtered],
  );

  async function handleCreate() {
    if (creating) return;
    setCreating(true);
    try {
      await createRemote("New chat");
    } catch {
      createLocal();
    } finally {
      setCreating(false);
    }
  }

  function handleRowKey(event: KeyboardEvent<HTMLButtonElement>, id: string) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      setActive(id);
    }
  }

  function handleMoreClick(event: MouseEvent<HTMLButtonElement>, id: string) {
    event.stopPropagation();
    setOpenMenuId((prev) => (prev === id ? null : id));
  }

  async function handleSweep(option: SweepOption) {
    setSweepOpen(false);
    // Count the conversations that would actually be deleted so the confirm
    // dialog tells the user what's about to happen. Pinned and frozen
    // conversations are preserved by default on the backend.
    const now = Date.now();
    const isProtected = (c: Conversation) =>
      c.pinned || typeof c.frozenAt === "number";
    const eligible = conversations.filter((c) => {
      if (isProtected(c)) return false;
      if (option.kind === "older") {
        const age = now - c.updatedAt;
        return age > option.days * MS_PER_DAY;
      }
      return true;
    });
    if (eligible.length === 0) {
      window.alert(
        option.kind === "older"
          ? `No conversations older than ${option.label}.`
          : "No conversations to delete.",
      );
      return;
    }
    const prompt =
      option.kind === "older"
        ? `Delete ${eligible.length} conversation(s) older than ${option.label}?\n\nPinned and checkpointed chats are kept.`
        : `Delete ${eligible.length} conversation(s)?\n\nPinned and checkpointed chats are kept.`;
    if (!window.confirm(prompt)) return;
    try {
      const result = await bulkDelete(
        option.kind === "older"
          ? { olderThanMs: now - option.days * MS_PER_DAY }
          : {},
      );
      if (result.preservedCount > 0) {
        // Silent — the "kept" count matches what the confirm dialog already
        // promised. No toast noise for an expected outcome.
      }
    } catch (err) {
      window.alert(
        `Failed to delete: ${err instanceof Error ? err.message : String(err)}`,
      );
    }
  }

  return (
    <aside
      className="relative flex h-full flex-col border-r border-line-2 bg-bg-1"
      style={{ width: threadW, minWidth: THREAD_W_MIN, maxWidth: THREAD_W_MAX }}
      aria-label="Conversation list"
    >
      {/* Header */}
      <div className="flex items-center gap-2 px-3 pt-3 pb-2">
        <span className="label-cap flex-1">Chats</span>
        <div ref={sweepContainerRef} className="relative">
          <button
            type="button"
            onClick={() => setSweepOpen((v) => !v)}
            aria-label="Delete conversations"
            aria-haspopup="menu"
            aria-expanded={sweepOpen}
            className={cn(
              "inline-flex h-6 w-6 items-center justify-center rounded",
              "text-fg-3 hover:text-danger hover:bg-bg-2 focus-ring",
            )}
          >
            <Trash2 className="h-3.5 w-3.5" aria-hidden />
          </button>
          {sweepOpen && (
            <div
              role="menu"
              aria-label="Delete conversations"
              className={cn(
                "absolute right-0 top-7 z-20 min-w-[10rem] py-1",
                "rounded border border-line-2 bg-bg-1 shadow-lg text-[12px]",
              )}
            >
              <div className="px-3 py-1 label-cap text-fg-3">Delete</div>
              {SWEEP_OPTIONS.map((opt) => {
                const label =
                  opt.kind === "all"
                    ? "All conversations"
                    : `Older than ${opt.label}`;
                return (
                  <button
                    key={opt.kind === "all" ? "all" : `older-${opt.days}`}
                    type="button"
                    role="menuitem"
                    className="block w-full px-3 py-1 text-left text-danger hover:bg-bg-2"
                    onClick={() => handleSweep(opt)}
                  >
                    {label}
                  </button>
                );
              })}
              <div className="px-3 pt-1 pb-0.5 text-[10px] text-fg-3">
                Pinned &amp; checkpoints kept.
              </div>
            </div>
          )}
        </div>
        <button
          type="button"
          onClick={handleCreate}
          disabled={creating}
          aria-label="New chat"
          className={cn(
            "inline-flex h-6 w-6 items-center justify-center rounded",
            "text-fg-2 hover:text-acc hover:bg-bg-2 focus-ring",
            "disabled:opacity-50 disabled:cursor-not-allowed",
          )}
        >
          <Plus className="h-3.5 w-3.5" aria-hidden />
        </button>
        <button
          type="button"
          onClick={toggleThreads}
          aria-label="Collapse thread list"
          className={cn(
            "inline-flex h-6 w-6 items-center justify-center rounded",
            "text-fg-3 hover:text-fg-0 hover:bg-bg-2 focus-ring",
          )}
        >
          <ChevronLeft className="h-3.5 w-3.5" aria-hidden />
        </button>
      </div>

      {/* Filter */}
      <div className="px-3 pb-2">
        <input
          type="text"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filter titles…"
          aria-label="Filter conversations by title"
          className={cn(
            "w-full rounded border border-line-2 bg-bg-2 px-2 py-1",
            "text-[12px] text-fg-1 placeholder:text-fg-3",
            "focus-ring focus:border-acc",
          )}
        />
      </div>

      {/* Body */}
      <div
        ref={menuContainerRef}
        className="relative flex-1 overflow-y-auto"
        role="list"
        aria-label="Conversations"
      >
        {sections.map((section) => {
          if (section.items.length === 0) return null;
          return (
            <div key={section.id} className="pb-1">
              <div className="flex items-center justify-between px-3 pt-2 pb-1">
                <span className="label-cap">{section.label}</span>
                <span className="mono text-[10px] text-fg-3">
                  {section.items.length}
                </span>
              </div>
              {section.items.map((conv) => {
                const isActive = conv.id === activeId;
                const frozen = isFrozen(conv);
                const isMenuOpen = openMenuId === conv.id;
                return (
                  <div key={conv.id} className="relative">
                    <button
                      type="button"
                      role="listitem"
                      aria-current={isActive ? "true" : undefined}
                      onClick={() => setActive(conv.id)}
                      onKeyDown={(e) => handleRowKey(e, conv.id)}
                      className={cn(
                        "relative w-full px-3 py-2 text-left transition-colors",
                        "focus-ring",
                        isActive
                          ? "bg-acc-dim text-fg-0"
                          : "text-fg-1 hover:bg-bg-2",
                        frozen && !isActive && "text-fg-2",
                      )}
                    >
                      {isActive && (
                        <span
                          aria-hidden
                          className="pointer-events-none absolute inset-y-1.5 left-0 w-0.5 bg-acc"
                        />
                      )}
                      <div className="flex items-center gap-1.5 pr-6">
                        {conv.pinned && !frozen && (
                          <Pin
                            className="h-2.5 w-2.5 shrink-0 text-acc"
                            aria-label="Pinned"
                          />
                        )}
                        {frozen && (
                          <Lock
                            className="h-2.5 w-2.5 shrink-0 text-fg-3"
                            aria-label="Frozen"
                          />
                        )}
                        <span
                          className={cn(
                            "flex-1 truncate text-[12.5px]",
                            isActive ? "font-medium" : "font-normal",
                          )}
                        >
                          {conv.title}
                        </span>
                        <span className="mono text-[10.5px] text-fg-3 shrink-0">
                          {relativeTime(conv.updatedAt, Date.now())}
                        </span>
                      </div>
                      <div className="mt-0.5 truncate pr-6 text-[11.5px] text-fg-3">
                        {previewOf(conv)}
                      </div>
                    </button>
                    <button
                      type="button"
                      onClick={(e) => handleMoreClick(e, conv.id)}
                      aria-label={`More options for ${conv.title}`}
                      aria-haspopup="menu"
                      aria-expanded={isMenuOpen}
                      className={cn(
                        "absolute right-1 top-1.5 inline-flex h-5 w-5",
                        "items-center justify-center rounded text-fg-3",
                        "hover:text-fg-0 hover:bg-bg-2 focus-ring",
                      )}
                    >
                      <MoreHorizontal className="h-3 w-3" aria-hidden />
                    </button>
                    {isMenuOpen && (
                      <MoreMenu
                        conversation={conv}
                        onClose={() => setOpenMenuId(null)}
                      />
                    )}
                  </div>
                );
              })}
            </div>
          );
        })}
        {conversations.length === 0 && (
          <div className="px-3 py-8 text-center text-[12px] text-fg-3">
            <div className="mb-1">No chats yet</div>
            <div className="mono text-[10.5px]">⌘N to start</div>
          </div>
        )}
        {conversations.length > 0 && filtered.length === 0 && (
          <div className="px-3 py-6 text-center text-[12px] text-fg-3">
            No matching titles
          </div>
        )}
      </div>

      {/* Right-edge resizer */}
      <div
        className="absolute top-0 right-0 h-full"
        style={{ transform: "translateX(2px)" }}
      >
        <Resizer
          axis="x"
          min={THREAD_W_MIN}
          max={THREAD_W_MAX}
          value={threadW}
          onChange={setThreadW}
          ariaLabel="Resize thread list"
          className="h-full"
        />
      </div>
    </aside>
  );
}
