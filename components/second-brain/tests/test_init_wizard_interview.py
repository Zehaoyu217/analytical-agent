from __future__ import annotations

from second_brain.habits import Habits
from second_brain.init_wizard.interview import InterviewAnswers, run_interview


def test_run_interview_non_interactive_yields_defaults():
    answers = run_interview(interactive=False)
    assert isinstance(answers, InterviewAnswers)
    assert answers.to_habits() == Habits.default()


def test_interview_answers_apply_density_override():
    answers = InterviewAnswers(default_density="dense")
    habits = answers.to_habits()
    assert habits.extraction.default_density == "dense"


def test_interview_answers_apply_retrieval_prefer():
    answers = InterviewAnswers(retrieval_prefer="sources")
    habits = answers.to_habits()
    assert habits.retrieval.prefer == "sources"


def test_interview_answers_apply_taxonomy_roots():
    answers = InterviewAnswers(taxonomy_roots=["papers/ml", "notes/personal"])
    habits = answers.to_habits()
    assert habits.taxonomy.roots == ["papers/ml", "notes/personal"]
