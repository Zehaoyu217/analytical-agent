"""Batch runner — trajectory generation for eval data and offline testing (H5).

Reads prompts from a JSONL file (one ``{"prompt": "..."}`` per line), runs each
through an ``AgentLoop``, and writes results to an output JSONL file.  Progress
is checkpointed every 10 completions so interrupted runs can resume.

Usage::

    python -m scripts.batch_runner \\
        --prompts prompts.jsonl \\
        --output results.jsonl \\
        [--resume]   # load existing checkpoint and skip completed indices

CLI args
--------
--prompts   Path to input JSONL (required)
--output    Path to output JSONL (default: batch_results.jsonl)
--resume    Resume from checkpoint if it exists
--max-steps Max agent steps per prompt (default: 12)
--model     Model name override (default: from config)
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_CHECKPOINT_INTERVAL = 10


@dataclass
class BatchResult:
    """Outcome of running a single prompt."""

    index: int
    prompt: str
    session_id: str
    final_text: str
    steps: int
    ok: bool
    error: str = ""
    duration_s: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class BatchSummary:
    """Aggregate summary across all results."""

    total: int
    completed: int
    failed: int
    avg_steps: float
    avg_duration_s: float
    results: list[BatchResult] = field(default_factory=list)


class BatchRunner:
    """Runs a list of prompts sequentially through the agent harness.

    Each prompt gets its own session (``source="batch"``) recorded in
    ``sessions.db`` so results are queryable and replayable.
    """

    def __init__(
        self,
        max_steps: int = 12,
        checkpoint_interval: int = _CHECKPOINT_INTERVAL,
    ) -> None:
        self._max_steps = max_steps
        self._checkpoint_interval = checkpoint_interval

    # ── Public API ──────────────────────────────────────────────────────────

    def run(
        self,
        prompts: list[str],
        output_path: Path,
        *,
        resume: bool = False,
    ) -> BatchSummary:
        """Run all *prompts* and write results to *output_path*.

        When *resume* is True and a checkpoint file exists, already-completed
        indices are skipped.
        """
        checkpoint_path = output_path.with_suffix(".checkpoint.json")
        completed_indices: set[int] = set()
        if resume and checkpoint_path.exists():
            completed_indices = self._load_checkpoint(checkpoint_path)
            logger.info(
                "Resuming: %d/%d prompts already completed",
                len(completed_indices), len(prompts),
            )

        results: list[BatchResult] = []
        for i, prompt in enumerate(prompts):
            if i in completed_indices:
                continue

            _t0 = time.monotonic()
            result = self.run_one(i, prompt)
            result.duration_s = time.monotonic() - _t0
            results.append(result)

            # Append result line immediately so partial output is usable.
            with open(output_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(asdict(result)) + "\n")

            # Print live progress.
            done = len(completed_indices) + len(results)
            avg_steps = sum(r.steps for r in results) / len(results)
            avg_dur = sum(r.duration_s for r in results) / len(results)
            print(
                f"[{done}/{len(prompts)}] "
                f"steps={result.steps} "
                f"avg_steps={avg_steps:.1f} "
                f"avg_dur={avg_dur:.1f}s "
                f"ok={result.ok}",
                flush=True,
            )

            # Checkpoint every N completions.
            if len(results) % self._checkpoint_interval == 0:
                all_done = completed_indices | {r.index for r in results}
                self._save_checkpoint(checkpoint_path, all_done)

        # Final checkpoint.
        all_done = completed_indices | {r.index for r in results}
        self._save_checkpoint(checkpoint_path, all_done)

        completed = [r for r in results if r.ok]
        failed = [r for r in results if not r.ok]
        return BatchSummary(
            total=len(prompts),
            completed=len(completed),
            failed=len(failed),
            avg_steps=sum(r.steps for r in results) / max(len(results), 1),
            avg_duration_s=sum(r.duration_s for r in results) / max(len(results), 1),
            results=results,
        )

    def run_one(self, index: int, prompt: str) -> BatchResult:
        """Run a single *prompt* through the agent and return a :class:`BatchResult`."""
        import uuid  # noqa: PLC0415

        from app.harness.dispatcher import ToolDispatcher  # noqa: PLC0415
        from app.harness.loop import AgentLoop  # noqa: PLC0415
        from app.harness.wiring import get_session_db  # noqa: PLC0415

        session_id = str(uuid.uuid4())
        db = get_session_db()
        db.create_session(
            id=session_id,
            model=None,
            goal=prompt[:300],
            source="batch",
        )

        try:
            client = self._build_client()
            system = self._build_system()
            loop = AgentLoop(dispatcher=ToolDispatcher())
            outcome = loop.run(
                client=client,
                system=system,
                user_message=prompt,
                dataset_loaded=False,
                max_steps=self._max_steps,
            )
            db.finalize_session(
                id=session_id,
                outcome=(outcome.final_text or "")[:500],
                step_count=outcome.steps,
            )
            return BatchResult(
                index=index,
                prompt=prompt,
                session_id=session_id,
                final_text=outcome.final_text or "",
                steps=outcome.steps,
                ok=True,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("batch prompt %d failed: %s", index, exc, exc_info=True)
            db.finalize_session(id=session_id, outcome=f"error: {exc}"[:500])
            return BatchResult(
                index=index,
                prompt=prompt,
                session_id=session_id,
                final_text="",
                steps=0,
                ok=False,
                error=str(exc),
            )

    # ── Private ────────────────────────────────────────────────────────────

    def _build_client(self) -> Any:
        import anthropic  # noqa: PLC0415

        from app.harness.clients.anthropic_client import AnthropicClient  # noqa: PLC0415
        from app.harness.config import ModelProfile  # noqa: PLC0415

        profile = ModelProfile(
            name="batch-worker",
            provider="anthropic",
            model_id="claude-haiku-4-5-20251001",
            tier="standard",
        )
        return AnthropicClient(profile=profile, api_client=anthropic.Anthropic())

    def _build_system(self) -> str:
        try:
            from app.harness.wiring import get_pre_turn_injector  # noqa: PLC0415
            return get_pre_turn_injector().build_static()
        except Exception:  # noqa: BLE001
            return "You are a helpful AI assistant."

    @staticmethod
    def _load_checkpoint(path: Path) -> set[int]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return set(data.get("completed", []))
        except Exception:  # noqa: BLE001
            return set()

    @staticmethod
    def _save_checkpoint(path: Path, completed: set[int]) -> None:
        path.write_text(
            json.dumps({"completed": sorted(completed)}),
            encoding="utf-8",
        )


# ── CLI entrypoint ─────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Run a batch of prompts through the agent harness.",
    )
    p.add_argument("--prompts", required=True, help="Path to input JSONL file")
    p.add_argument("--output", default="batch_results.jsonl", help="Path to output JSONL file")
    p.add_argument("--resume", action="store_true", help="Resume from checkpoint if available")
    p.add_argument("--max-steps", type=int, default=12)
    return p.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = _parse_args()

    prompts_path = Path(args.prompts)
    prompts: list[str] = []
    with open(prompts_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            prompts.append(obj.get("prompt", ""))

    if not prompts:
        print("No prompts found in input file.", file=sys.stderr)
        sys.exit(1)

    runner = BatchRunner(max_steps=args.max_steps)
    summary = runner.run(
        prompts=prompts,
        output_path=Path(args.output),
        resume=args.resume,
    )
    print(
        f"\nDone: {summary.completed}/{summary.total} completed, "
        f"{summary.failed} failed, "
        f"avg_steps={summary.avg_steps:.1f}, "
        f"avg_dur={summary.avg_duration_s:.1f}s"
    )


if __name__ == "__main__":
    main()
