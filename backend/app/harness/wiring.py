"""Process-wide singletons for the agent harness.

The harness is composed of long-lived stateful components — ArtifactStore (sqlite
+ disk), WikiEngine (filesystem), SkillRegistry (discover-once), GotchaIndex
(read-once), and PreTurnInjector (composes the four). Every chat request needs
the same instances; this module builds them lazily and caches them.

All accessors are idempotent: first call constructs, subsequent calls reuse.
Tests can override paths via the ``CCAGENT_*`` environment variables.

Runtime data paths default to subdirectories of ``CCAGENT_HOME`` (``~/.ccagent``
by default — see ``app.core.home``). Override individual paths with:
  CCAGENT_ARTIFACT_DB   — SQLite DB for artifacts
  CCAGENT_ARTIFACT_DISK — directory for large artifact blobs
  CCAGENT_WIKI_ROOT     — wiki root directory
  CCAGENT_SKILLS_ROOT   — skills package directory (source, not data)
  CCAGENT_PROMPT_PATH   — path to the base system prompt markdown
"""
from __future__ import annotations

import os
from pathlib import Path
from threading import RLock

from app.artifacts.store import ArtifactStore
from app.core.home import artifacts_db_path, artifacts_disk_path, sessions_db_path, wiki_root_path
from app.harness.injector import PreTurnInjector
from app.skills.registry import SkillRegistry
from app.storage.session_db import SessionDB
from app.wiki.engine import WikiEngine

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_REPO_ROOT = Path(__file__).resolve().parents[3]

# Skills root and prompt path are source-code paths, not runtime data —
# they stay relative to the repo rather than CCAGENT_HOME.
_DEFAULT_SKILLS_ROOT = _BACKEND_ROOT / "app" / "skills"
_DEFAULT_PROMPT_PATH = _REPO_ROOT / "prompts" / "data_scientist.md"

_lock = RLock()
_artifact_store: ArtifactStore | None = None
_session_db: SessionDB | None = None
_wiki_engine: WikiEngine | None = None
_skill_registry: SkillRegistry | None = None
_pre_turn_injector: PreTurnInjector | None = None
_cron_engine: Any = None  # CronEngine — late import avoids APScheduler at import time
_toolset_resolver: Any = None  # ToolsetResolver — late import


def _path_from_env(env_var: str, default: Path) -> Path:
    raw = os.environ.get(env_var)
    return Path(raw) if raw else default


def get_session_db() -> SessionDB:
    global _session_db
    if _session_db is not None:
        return _session_db
    with _lock:
        if _session_db is None:
            db_path = _path_from_env("CCAGENT_SESSION_DB", sessions_db_path())
            _session_db = SessionDB(db_path=db_path)
    return _session_db


def get_artifact_store() -> ArtifactStore:
    global _artifact_store
    if _artifact_store is not None:
        return _artifact_store
    with _lock:
        if _artifact_store is None:
            db = _path_from_env("CCAGENT_ARTIFACT_DB", artifacts_db_path())
            disk = _path_from_env("CCAGENT_ARTIFACT_DISK", artifacts_disk_path())
            db.parent.mkdir(parents=True, exist_ok=True)
            disk.mkdir(parents=True, exist_ok=True)
            _artifact_store = ArtifactStore(db_path=db, disk_root=disk)
    return _artifact_store


def get_wiki_engine() -> WikiEngine:
    global _wiki_engine
    if _wiki_engine is not None:
        return _wiki_engine
    with _lock:
        if _wiki_engine is None:
            root = _path_from_env("CCAGENT_WIKI_ROOT", wiki_root_path())
            root.mkdir(parents=True, exist_ok=True)
            (root / "findings").mkdir(exist_ok=True)
            (root / "hypotheses").mkdir(exist_ok=True)
            (root / "entities").mkdir(exist_ok=True)
            (root / "meta").mkdir(exist_ok=True)
            for fname in ("working.md", "log.md", "index.md"):
                fpath = root / fname
                if not fpath.exists():
                    fpath.write_text(f"# {fname.replace('.md', '').title()}\n\n")
            _wiki_engine = WikiEngine(root=root)
    return _wiki_engine


def get_skill_registry() -> SkillRegistry:
    global _skill_registry
    if _skill_registry is not None:
        return _skill_registry
    with _lock:
        if _skill_registry is None:
            root = _path_from_env("CCAGENT_SKILLS_ROOT", _DEFAULT_SKILLS_ROOT)
            registry = SkillRegistry(skills_root=root)
            registry.discover()
            _skill_registry = registry
    return _skill_registry


# ── Adapters ──────────────────────────────────────────────────────────────────


class _SkillMenuAdapter:
    """Adapt SkillRegistry to the PreTurnInjector _SkillRegistry protocol."""

    def __init__(self, registry: SkillRegistry) -> None:
        self._registry = registry

    def list_top_level(self) -> list:
        return self._registry.list_top_level()


class _WikiWrapUpAdapter:
    """Adapt WikiEngine to the TurnWrapUp wiki protocol.

    TurnWrapUp expects ``update_working``, ``promote_finding(**kwargs)``,
    ``append_log``, and ``rebuild_index``. WikiEngine has ``write_working``
    (raises if too long), ``promote_finding(Finding)``, and the rest.
    """

    _MAX_WORKING_LINES = 200

    def __init__(self, wiki: WikiEngine) -> None:
        self._wiki = wiki

    def update_working(self, content: str) -> None:
        # WikiEngine.write_working raises when content exceeds 200 lines.
        # The wrap-up should NOT crash the turn over a bloated scratchpad —
        # truncate to the limit and prepend a note so the agent sees it.
        lines = content.splitlines()
        if len(lines) > self._MAX_WORKING_LINES:
            kept = lines[: self._MAX_WORKING_LINES - 1]
            kept.insert(
                0,
                f"<!-- truncated: {len(lines)} lines → {self._MAX_WORKING_LINES} -->",
            )
            content = "\n".join(kept)
        self._wiki.write_working(content)

    def append_log(self, entry: str) -> None:
        self._wiki.append_log(entry)

    def rebuild_index(self) -> None:
        self._wiki.rebuild_index()

    def promote_finding(
        self,
        *,
        finding_id: str,
        body: str,
        evidence_ids: list[str],
        validated_by: str,
    ) -> None:
        from app.wiki.schema import Finding
        finding = Finding(
            id=finding_id,
            title=body[:80],
            body=body,
            evidence=list(evidence_ids),
            stat_validate_pass=bool(validated_by),
        )
        self._wiki.promote_finding(finding)

    def write_session_notes(self, session_id: str, notes: str) -> None:
        self._wiki.write_session_notes(session_id, notes)


def get_wiki_wrap_up_adapter() -> _WikiWrapUpAdapter:
    return _WikiWrapUpAdapter(get_wiki_engine())


class _WikiInjectorAdapter:
    """Adapt WikiEngine to the PreTurnInjector wiki protocol.

    The injector wants ``working_digest()`` and ``index_digest()`` — short text
    blobs to drop into the system prompt. We read the full files and let the
    injector decide how to render them.
    """

    _MAX_DIGEST_CHARS = 4000

    def __init__(self, wiki: WikiEngine) -> None:
        self._wiki = wiki

    def _read_truncated(self, name: str) -> str:
        path = self._wiki.root / name
        if not path.exists():
            return ""
        text = path.read_text(encoding="utf-8").strip()
        if len(text) <= self._MAX_DIGEST_CHARS:
            return text
        return text[: self._MAX_DIGEST_CHARS] + "\n…(truncated)"

    def working_digest(self) -> str:
        return self._read_truncated("working.md")

    def index_digest(self) -> str:
        return self._read_truncated("index.md")

    def latest_session_notes(self, exclude_session_id: str = "") -> str:
        text = self._wiki.latest_session_notes(exclude_session_id=exclude_session_id)
        if len(text) <= self._MAX_DIGEST_CHARS:
            return text
        return text[: self._MAX_DIGEST_CHARS] + "\n…(truncated)"


def get_pre_turn_injector() -> PreTurnInjector:
    global _pre_turn_injector
    if _pre_turn_injector is not None:
        return _pre_turn_injector
    with _lock:
        if _pre_turn_injector is None:
            from app.config import load_branding  # noqa: PLC0415
            prompt_path = _path_from_env("CCAGENT_PROMPT_PATH", _DEFAULT_PROMPT_PATH)
            wiki = get_wiki_engine()
            registry = get_skill_registry()
            branding = load_branding()
            _pre_turn_injector = PreTurnInjector(
                prompt_path=prompt_path,
                wiki=_WikiInjectorAdapter(wiki),
                skill_registry=_SkillMenuAdapter(registry),
                agent_persona=branding.agent_persona,
            )
    return _pre_turn_injector


_DEFAULT_TOOLSETS_PATH = _BACKEND_ROOT / "config" / "toolsets.yaml"


def get_toolset_resolver() -> Any:
    """Return the process-wide ToolsetResolver singleton."""
    global _toolset_resolver
    if _toolset_resolver is not None:
        return _toolset_resolver
    with _lock:
        if _toolset_resolver is None:
            from app.harness.toolsets import ToolsetResolver  # noqa: PLC0415

            ts_path = _path_from_env("CCAGENT_TOOLSETS_PATH", _DEFAULT_TOOLSETS_PATH)
            _toolset_resolver = ToolsetResolver.from_yaml(ts_path)
    return _toolset_resolver


class _MinimalCronFactory:
    """Minimal AgentFactory for cron job execution.

    Builds a bare-bones loop (no registered tools) backed by the Anthropic API.
    For production use with the full data-science tool catalog, supply a custom
    factory via ``get_cron_engine(agent_factory=...)``.
    """

    def build_loop(self, session_id: str) -> Any:
        from app.harness.dispatcher import ToolDispatcher  # noqa: PLC0415
        from app.harness.loop import AgentLoop  # noqa: PLC0415

        return AgentLoop(dispatcher=ToolDispatcher())

    def build_client(self) -> Any:
        import anthropic  # noqa: PLC0415

        from app.harness.clients.anthropic_client import AnthropicClient  # noqa: PLC0415
        from app.harness.config import ModelProfile  # noqa: PLC0415

        profile = ModelProfile(
            name="cron-worker",
            provider="anthropic",
            model_id="claude-haiku-4-5-20251001",
            tier="standard",
        )
        return AnthropicClient(profile=profile, api_client=anthropic.Anthropic())

    def build_system(self) -> str:
        try:
            return get_pre_turn_injector().build_static()
        except Exception:  # noqa: BLE001
            return "You are a helpful AI assistant running a scheduled analysis job."


def get_cron_engine(agent_factory: Any = None) -> Any:
    """Return the process-wide CronEngine singleton.

    Pass *agent_factory* the first time to override the default minimal factory.
    Subsequent calls with a factory argument are ignored (singleton is already built).
    """
    global _cron_engine
    if _cron_engine is not None:
        return _cron_engine
    with _lock:
        if _cron_engine is None:
            from app.scheduler.engine import CronEngine  # noqa: PLC0415

            _cron_engine = CronEngine(
                session_db=get_session_db(),
                agent_factory=agent_factory or _MinimalCronFactory(),
            )
    return _cron_engine


def reset_singletons_for_tests() -> None:
    """Clear cached singletons so tests get fresh instances."""
    global _artifact_store, _session_db, _wiki_engine, _skill_registry, _pre_turn_injector, _cron_engine, _toolset_resolver
    with _lock:
        _artifact_store = None
        _session_db = None
        _wiki_engine = None
        _skill_registry = None
        _pre_turn_injector = None
        _cron_engine = None
        _toolset_resolver = None
