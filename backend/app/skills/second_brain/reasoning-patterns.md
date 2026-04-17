---
name: second_brain_reasoning_patterns
description: "[Reference] Walking the Second Brain graph — query templates, contradiction handling, depth heuristics."
---

# Reasoning patterns

## Pattern 1 — grounded answer

```
sb_search(query=<user question>, k=10, scope="claims")
→ for each top-3 hit:
    sb_load(node_id=hit.id, depth=1)
→ draft answer, cite clm_ ids
```

## Pattern 2 — "why" / causal chain

```
sb_search(query=<topic>, scope="claims") → pick root
sb_reason(start_id=<root>, walk="supports", direction="inbound", max_depth=3)
→ explain chain top-down
```

## Pattern 3 — contradiction audit

```
sb_search(query=<topic>) → pick seed
sb_reason(start_id=<seed>, walk="contradicts", max_depth=2)
→ list open contradictions (rationale empty)
→ surface to user; don't pick a winner unilaterally
```

## Depth heuristics

- `depth=0`: fact lookup, minimal context.
- `depth=1`: normal research question.
- `depth=2+`: "explain the chain", "audit the topic". Expensive — justify.

## Anti-patterns

- **Don't** answer from memory when `sb_search` returned hits. The KB is the
  user's curated truth; your memory is the fallback.
- **Don't** call `sb_ingest` on arbitrary URLs during conversation — it mutates
  disk. Ask the user first, unless explicitly told to scrape.
- **Don't** use `sb_promote_claim` to store conversational summaries. Claims
  must be atomic + falsifiable.
