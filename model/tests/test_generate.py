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
        if family == "unsupported":
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
        if name == "unsupported":  # these may say what happens: they are refused anyway
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
