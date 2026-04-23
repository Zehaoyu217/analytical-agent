"""Turn interactive prompts into `Habits` overrides. Interactive logic is kept
thin — prompts live here; the scaffold + CLI layers stay decoupled.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import click

from second_brain.habits import Habits
from second_brain.habits.schema import Density, RetrievalPref


@dataclass(frozen=True)
class InterviewAnswers:
    taxonomy_roots: list[str] | None = None
    default_density: Density | None = None
    retrieval_prefer: RetrievalPref | None = None
    # Accepted but currently no-op — InjectionHabits has no `scope` field in
    # the schema; runtime scope is passed via `sb inject --scope`.
    injection_scope: Literal["claims", "sources", "both"] | None = None
    # Accepted but currently no-op — Autonomy uses `default` + per-op
    # `overrides` dict rather than a dedicated `extract` field.
    autonomy_extract: Literal["auto", "hitl"] | None = None

    def to_habits(self) -> Habits:
        base = Habits.default()
        patch: dict = {}

        if self.taxonomy_roots is not None:
            patch["taxonomy"] = base.taxonomy.model_copy(
                update={"roots": list(self.taxonomy_roots)}
            )
        if self.default_density is not None:
            patch["extraction"] = base.extraction.model_copy(
                update={"default_density": self.default_density}
            )
        if self.retrieval_prefer is not None:
            patch["retrieval"] = base.retrieval.model_copy(
                update={"prefer": self.retrieval_prefer}
            )
        # injection_scope / autonomy_extract intentionally not applied: the
        # current habits schema carries no matching field. They are retained
        # on InterviewAnswers so the wizard prompt can still capture intent
        # for future schema growth.

        return base.model_copy(update=patch) if patch else base


def run_interview(interactive: bool = True) -> InterviewAnswers:
    """Run the wizard interview. Defaults-only when `interactive=False`."""
    if not interactive:
        return InterviewAnswers()

    click.echo(
        "Second Brain setup — answer a few questions "
        "(press Enter for defaults).\n"
    )

    taxonomy_input = click.prompt(
        "Taxonomy roots (comma-separated, blank = defaults)",
        default="",
        show_default=False,
    ).strip()
    taxonomy_roots = (
        [r.strip() for r in taxonomy_input.split(",") if r.strip()]
        if taxonomy_input
        else None
    )

    density = click.prompt(
        "Default claim-extraction density",
        type=click.Choice(["sparse", "moderate", "dense"]),
        default="moderate",
    )

    prefer = click.prompt(
        "Retrieval preference",
        type=click.Choice(["claims", "sources", "balanced"]),
        default="claims",
    )

    scope = click.prompt(
        "Prompt-injection scope",
        type=click.Choice(["claims", "sources", "both"]),
        default="claims",
    )

    autonomy = click.prompt(
        "Claim extraction autonomy",
        type=click.Choice(["auto", "hitl"]),
        default="auto",
    )

    return InterviewAnswers(
        taxonomy_roots=taxonomy_roots,
        default_density=density,
        retrieval_prefer=prefer,
        injection_scope=scope,
        autonomy_extract=autonomy,
    )
