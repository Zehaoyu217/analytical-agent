from __future__ import annotations

from pathlib import Path

from app.evals.rubric import load_rubric

SAMPLE_RUBRIC_YAML = """\
level: 1
name: "Basic Rendering"
prompt: "Show me a chart."
dimensions:
  chart_correctness:
    weight: 0.5
    type: llm_judge
    criteria:
      A: "Perfect chart"
      B: "Good chart"
      C: "Okay chart"
  table_correctness:
    weight: 0.5
    type: hybrid
    deterministic:
      - "output contains 10 rows"
    criteria:
      A: "Perfect table"
      B: "Good table"
      C: "Okay table"
grading:
  A: 0.85
  B: 0.60
  C: 0.40
"""

SEQUENCE_RUBRIC_YAML = """\
level: 5
name: "Stress Test"
prompt_sequence:
  - "Step one"
  - "Step two"
  - "Step three"
dimensions:
  step_completion:
    weight: 1.0
    type: deterministic
    criteria:
      A: "All steps"
      B: "Most steps"
      C: "Some steps"
grading:
  A: 0.85
  B: 0.60
  C: 0.40
token_budget_optimal: 4000
"""


def test_load_rubric_basic(tmp_path: Path) -> None:
    rubric_file = tmp_path / "test.yaml"
    rubric_file.write_text(SAMPLE_RUBRIC_YAML)
    rubric = load_rubric(rubric_file)
    assert rubric.level == 1
    assert rubric.name == "Basic Rendering"
    assert rubric.prompt == "Show me a chart."
    assert len(rubric.dimensions) == 2


def test_load_rubric_dimension_types(tmp_path: Path) -> None:
    rubric_file = tmp_path / "test.yaml"
    rubric_file.write_text(SAMPLE_RUBRIC_YAML)
    rubric = load_rubric(rubric_file)
    chart = rubric.dimensions["chart_correctness"]
    assert chart.type == "llm_judge"
    assert chart.weight == 0.5
    assert chart.criteria["A"] == "Perfect chart"
    assert chart.deterministic == []


def test_load_rubric_hybrid_has_deterministic(tmp_path: Path) -> None:
    rubric_file = tmp_path / "test.yaml"
    rubric_file.write_text(SAMPLE_RUBRIC_YAML)
    rubric = load_rubric(rubric_file)
    table = rubric.dimensions["table_correctness"]
    assert table.type == "hybrid"
    assert table.deterministic == ["output contains 10 rows"]


def test_load_rubric_grading_thresholds(tmp_path: Path) -> None:
    rubric_file = tmp_path / "test.yaml"
    rubric_file.write_text(SAMPLE_RUBRIC_YAML)
    rubric = load_rubric(rubric_file)
    assert rubric.grading_thresholds == {"A": 0.85, "B": 0.60, "C": 0.40}


def test_load_rubric_prompt_sequence(tmp_path: Path) -> None:
    rubric_file = tmp_path / "test.yaml"
    rubric_file.write_text(SEQUENCE_RUBRIC_YAML)
    rubric = load_rubric(rubric_file)
    assert rubric.prompt == ""
    assert rubric.prompt_sequence == ["Step one", "Step two", "Step three"]
    assert rubric.token_budget_optimal == 4000


def test_load_rubric_no_token_budget(tmp_path: Path) -> None:
    rubric_file = tmp_path / "test.yaml"
    rubric_file.write_text(SAMPLE_RUBRIC_YAML)
    rubric = load_rubric(rubric_file)
    assert rubric.token_budget_optimal is None
