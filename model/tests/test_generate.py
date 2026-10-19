import json
import random

import jsonschema
import pytest

from parser_model import paths
from parser_model.generate import FAMILIES, fix_articles, make_problems, verify
from parser_model.grounding import check_grounding
from parser_model.phrasing import be
from parser_model.prompts import finetune_messages


def test_article_and_plural_helpers():
    assert fix_articles("A 8 kg block and a 80 N push, a 5 kg ball, A 11 m rope") == (
        "An 8 kg block and an 80 N push, a 5 kg ball, An 11 m rope"
    )
    assert fix_articles("a height of 80 m") == "a height of 80 m"
    assert be(1) == "is" and be(3) == "are"


def test_generation_is_deterministic():
    a = [(i, p.scene, p.questions) for i, p in make_problems(30, seed=5)]
    b = [(i, p.scene, p.questions) for i, p in make_problems(30, seed=5)]
    assert a == b
    assert a != [(i, p.scene, p.questions) for i, p in make_problems(30, seed=6)]


@pytest.mark.parametrize("family", sorted(FAMILIES))
def test_every_family_yields_schema_valid_grounded_scenes(family):
    validator = jsonschema.Draft202012Validator(paths.load_schema())
    rng = random.Random(11)
    for _ in range(40):
        problem = FAMILIES[family](rng)
        if family in ("unsupported", "partial"):
            assert set(problem.scene) == {"unsupported"} and problem.scene["unsupported"]
            assert set(problem.questions) == {"textbook", "casual", "terse"}
            continue
        assert validator.is_valid(problem.scene), problem.scene
        assert set(problem.questions) == {"textbook", "casual", "terse"}
        assert set(problem.expected) == {q["id"] for q in problem.scene["queries"]}
        for style, question in problem.questions.items():
            result = check_grounding(fix_articles(question), problem.scene)
            assert result.grounded, (family, style, question, result.ungrounded)


def test_questions_never_leak_outcomes():
    banned = ("slides", "sticks", "stays put", "does not move", "won't move")
    rng = random.Random(2)
    for name, make in FAMILIES.items():
        if name in ("unsupported", "partial"):  # refused anyway, so they may say what happens
            continue
        for _ in range(30):
            for question in make(rng).questions.values():
                assert not any(word in question.lower() for word in banned), question


def test_finetune_prompt_has_no_schema_or_examples():
    system = finetune_messages("A 5 kg block.")[0]["content"]
    assert "$schema" not in system and "Examples" not in system
    assert len(system) < 1200


@pytest.mark.solver
@pytest.mark.parametrize("family", sorted(FAMILIES))
def test_closed_form_answers_match_the_real_solver(family):
    rng = random.Random(3)
    for _ in range(6):
        problem = FAMILIES[family](rng)
        assert verify(problem) == [], json.dumps(problem.scene)


def test_paraphrase_filter():
    from parser_model.paraphrase import keep

    scene = {"queries": [{"id": "a", "ask": "acceleration", "body": "b", "at": 1}]}
    original = "A 5 kg block is pushed with 20 N. Find its acceleration at t = 1 s."
    good = "I shove a 5 kg block with a 20 N push. How is it accelerating after 1 s, in m/s^2?"
    assert keep(original, good + " Please compute the acceleration.", scene) is None
    assert (
        keep(original, "A 6 kg block is pushed with 20 N. What is its acceleration at 1 s?", scene)
        == "numbers"
    )
    assert (
        keep(
            original,
            "A 5 kg block is pushed with 20 N. What is its velocity at 1 s, I wonder?",
            scene,
        )
        == "asks"
    )
    assert (
        keep(
            original,
            "A 5 kg block is pushed with 20 N and slides. Find its acceleration at 1 s.",
            scene,
        )
        == "leak"
    )


def test_unsupported_categories_all_render():
    from parser_model.unsupported import CATEGORIES

    rng = random.Random(1)
    for name, make in CATEGORIES.items():
        for text in make(rng):
            assert len(text) > 10, name


def test_friction_given_modes():
    from parser_model.generate import friction_given

    rng = random.Random(4)
    seen = {"both": 0, "kinetic": 0, "single": 0}
    for _ in range(400):
        mu_s, mu_k, mode = friction_given(rng, 0.5, 0.4)
        seen[mode] += 1
        assert (mu_s == mu_k == 0.4) if mode != "both" else (mu_s, mu_k) == (0.5, 0.4)
    assert all(v > 20 for v in seen.values())
    assert friction_given(rng, 0.0, 0.0) == (0.0, 0.0, "both")


def test_partial_refusals_extend_an_in_scope_question():
    from parser_model.generate import partial_problem

    rng = random.Random(8)
    for _ in range(20):
        p = partial_problem(rng)
        assert set(p.scene) == {"unsupported"}
        assert all(len(q) > 40 for q in p.questions.values())
        assert any(w in p.questions["textbook"].lower() for w in ("also", "in addition"))


def test_dataset_drops_val_test_questions_that_also_appear_in_train(tmp_path):
    from parser_model.dataset import make_dataset
    from parser_model.splits import split_of

    base = {"family": "x", "style": "terse", "scene": {"version": 1.1, "bodies": []}}
    records = []
    for n in range(400):  # many problems, a few of which render the same question text
        records.append({**base, "id": f"p{n}", "parent": f"p{n}", "question": f"q {n % 120}"})
    splits_of = {r["id"]: split_of(r) for r in records}
    assert {"train", "val", "test"} <= set(splits_of.values())
    summary = make_dataset(records, tmp_path)
    assert summary["dropped_val_test_questions_also_in_train"] > 0
    train_q = {
        json.loads(line)["messages"][1]["content"]
        for line in (tmp_path / "train.jsonl").read_text().splitlines()
    }
    for name in ("val", "test"):
        for line in (tmp_path / f"{name}.jsonl").read_text().splitlines():
            row = json.loads(line)
            q = (
                row["messages"][1]["content"]
                if "messages" in row
                else f"Problem: {row['question']}\nJSON:"
            )
            assert q not in train_q


def test_paraphrase_drift_filter():
    from parser_model.paraphrase import drifted

    stretched = "A 2 kg block on a spring of 100 N/m is stretched by 0.5 m and released."
    assert drifted(stretched, "A 2 kg block on a spring is compressed by 0.5 m and released.")
    assert not drifted(
        stretched, "A 2 kg block hangs on a 100 N/m spring pulled out 0.5 m, released."
    )
    assert not drifted(
        stretched, "Ignore air resistance. A 2 kg block on a spring, stretched 0.5 m."
    )
    assert drifted(stretched, "The 2 kg block bounces back from the wall after release.")


def test_family_restricted_generation():
    from parser_model.generate import make_problems

    only = make_problems(20, 1, prefix="x", families=["unsupported", "partial"])
    assert {p.family for _, p in only} <= {"unsupported", "partial"}
    assert all(pid.startswith("x-") for pid, _ in only)
