from second_brain.habits import Habits
from second_brain.habits.density import resolve_density


def test_explicit_density_wins():
    h = Habits.default()
    assert resolve_density(kind="url", taxonomy="papers/ml", habits=h, explicit="dense") == "dense"


def test_by_kind_beats_by_taxonomy_and_default():
    h = Habits.default()
    # url kind forces sparse even though papers/ml taxonomy prefers dense.
    assert resolve_density(kind="url", taxonomy="papers/ml", habits=h, explicit=None) == "sparse"


def test_by_taxonomy_prefix_match():
    h = Habits.default()
    assert resolve_density(kind="pdf", taxonomy="papers/ml", habits=h, explicit=None) == "dense"
    assert resolve_density(kind="pdf", taxonomy="blog/personal", habits=h, explicit=None) == "sparse"


def test_most_specific_taxonomy_prefix_wins():
    h = Habits.default().model_copy(update={
        "extraction": Habits.default().extraction.model_copy(update={
            "by_taxonomy": {"papers/*": "dense", "papers/ml/thesis/*": "moderate"},
        }),
    })
    assert resolve_density(kind="pdf", taxonomy="papers/ml/thesis/2021",
                           habits=h, explicit=None) == "moderate"


def test_default_density_when_no_match():
    h = Habits.default()
    assert resolve_density(kind="note", taxonomy=None, habits=h, explicit=None) == "moderate"
