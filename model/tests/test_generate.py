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
        assert validator.is_valid(problem.scene), problem.scene
        assert set(problem.questions) == {"textbook", "casual", "terse"}
        assert set(problem.expected) == {q["id"] for q in problem.scene["queries"]}
        for style, question in problem.questions.items():
            result = check_grounding(fix_articles(question), problem.scene)
            assert result.grounded, (family, style, question, result.ungrounded)


def test_questions_never_leak_outcomes():
    banned = ("slides", "sticks", "stays put", "does not move", "won't move")
    rng = random.Random(2)
    for make in FAMILIES.values():
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
