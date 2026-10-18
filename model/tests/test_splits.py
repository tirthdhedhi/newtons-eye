import pytest

from parser_model import paths
from parser_model.splits import assign, check_no_leakage, split_of


def rec(id, parent=None, **kw):
    return {"id": id, "question": f"question {id}", **({"parent": parent} if parent else {}), **kw}


def test_variants_follow_their_parent():
    for n in range(200):
        parent = f"p{n}"
        splits = {split_of(rec(f"{parent}-v{k}", parent)) for k in range(4)}
        assert splits == {split_of(rec(parent))}


def test_roughly_70_10_20():
    out = assign([rec(f"p{n}") for n in range(2000)])
    shares = {k: len(v) / 2000 for k, v in out.items()}
    assert shares["train"] == pytest.approx(0.7, abs=0.04)
    assert shares["val"] == pytest.approx(0.1, abs=0.03)
    assert shares["test"] == pytest.approx(0.2, abs=0.04)


def test_assignment_is_stable_when_records_are_added():
    before = {f"p{n}": split_of(rec(f"p{n}")) for n in range(100)}
    assign([rec(f"p{n}") for n in range(500)])
    assert before == {f"p{n}": split_of(rec(f"p{n}")) for n in range(100)}


def test_seed_and_holdout_family_are_always_test():
    assert all(split_of(rec(f"s{n}", source="seed")) == "test" for n in range(50))
    assert all(split_of(rec(f"f{n}", family="spring"), ["spring"]) == "test" for n in range(50))
    assert any(split_of(rec(f"f{n}", family="spring")) == "train" for n in range(50))


def test_the_real_seed_set_is_all_test():
    seed = paths.load_seed(paths.model_dir() / "data" / "seed.jsonl")
    assert {split_of({**r, "source": "seed"}) for r in seed} == {"test"}


def test_leakage_checks():
    ok = {"train": [rec("a")], "val": [rec("b")], "test": [rec("c")]}
    check_no_leakage(ok)
    with pytest.raises(ValueError, match="shares parent"):
        check_no_leakage({"train": [rec("a")], "val": [], "test": [rec("a-v1", "a")]})
    dup = {**rec("z"), "question": "A 5 kg block!"}
    with pytest.raises(ValueError, match="same question"):
        check_no_leakage({"train": [rec("a", question="a 5 kg  block")], "val": [], "test": [dup]})
