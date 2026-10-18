import json

import pytest

from parser_model import paths
from parser_model.metrics import GoldCache, evaluate_item, summarize
from parser_model.solve import SolveResult

SCHEMA = {
    "type": "object",
    "properties": {"version": {"const": 1.1}, "bodies": {"type": "array"}},
    "required": ["version", "bodies"],
}
ITEM = {
    "id": "toy/textbook",
    "example": "toy",
    "style": "textbook",
    "question": "A 5 kg block is pushed with 50 N. Find its acceleration at t = 1 s.",
}
GOLD_SCENE = {
    "version": 1,
    "bodies": [{"id": "block", "mass": "5 kg"}],
    "queries": [{"id": "a", "ask": "acceleration", "body": "block", "at": 1}],
}


def good_scene(**over):
    scene = {
        "version": 1.1,
        "bodies": [{"id": "box", "mass": "5 kg"}],
        "queries": [{"id": "x", "ask": "acceleration", "body": "box", "at": 1}],
    }
    return {**scene, **over}


class FakeSolver:
    """Stands in for the pnpm solver: answers by a fixed table, keyed on the first query id."""

    def __init__(self, answers=None, result=None):
        self.answers = answers if answers is not None else {}
        self.result = result
        self.calls = 0

    def __call__(self, scene):
        self.calls += 1
        if self.result is not None:
            return self.result
        qid = scene["queries"][0]["id"]
        return SolveResult(exit_code=0, answers={qid: self.answers.get("a", 10.0)})


def run(raw, solver=None, gold_answer=10.0):
    gold_solver = FakeSolver({"a": gold_answer})
    gold = GoldCache(lambda ex: GOLD_SCENE, gold_solver)
    solver = solver or FakeSolver()
    return evaluate_item(ITEM, raw, schema=SCHEMA, gold=gold, solver=solver)


def test_perfect_item():
    r = run(json.dumps(good_scene()))
    assert [r.valid_json, r.schema_valid, r.solver_ok, r.grounded, r.solver_match] == [True] * 5
    assert r.failures == [] and r.failure_reason == ""


def test_invalid_json():
    r = run("Sure! Here is the scene: {")
    assert not r.valid_json
    assert r.failure_reason.startswith("invalid_json")
    assert r.scene is None


def test_fenced_json_and_think_block_are_accepted():
    raw = "<think>hmm</think>\n```json\n" + json.dumps(good_scene()) + "\n```"
    assert run(raw).valid_json


def test_non_object_json():
    r = run("[1, 2]")
    assert not r.valid_json
    assert "not an object" in r.failure_reason


def test_schema_failure_still_runs_other_metrics():
    r = run(json.dumps(good_scene(version=1.0)))
    assert r.valid_json and not r.schema_valid
    assert r.solver_ok and r.grounded and r.solver_match
    assert r.failure_reason.startswith("schema:")


def test_solver_validation_failure():
    bad = SolveResult(exit_code=1, issues=[{"path": "bodies", "message": "nope"}])
    r = run(json.dumps(good_scene()), solver=FakeSolver(result=bad))
    assert not r.solver_ok and not r.solver_match
    assert "solver_exit_1" in r.failure_reason


def test_solver_query_failure_is_not_ok():
    bad = SolveResult(exit_code=2, answers={"x": None}, errors=["x: boom"])
    r = run(json.dumps(good_scene()), solver=FakeSolver(result=bad))
    assert not r.solver_ok and not r.solver_match


def test_ungrounded_number():
    scene = good_scene(environment={"gravity": [0, -10, 0]})
    r = run(json.dumps(scene))
    assert not r.grounded and r.solver_ok and r.solver_match
    assert r.ungrounded[0]["path"] == "environment.gravity[1]"
    assert "ungrounded" in "".join(r.failures)


def test_wrong_answer():
    r = run(json.dumps(good_scene()), solver=FakeSolver({"a": 11.0}))
    assert r.solver_ok and not r.solver_match
    assert r.failure_reason.startswith("mismatch")


@pytest.mark.parametrize(("got", "match"), [(10.009, True), (10.02, False)])
def test_tolerance_edge(got, match):
    assert run(json.dumps(good_scene()), solver=FakeSolver({"a": got})).solver_match is match


def test_missing_query_is_a_mismatch():
    scene = good_scene(queries=[{"id": "x", "ask": "velocity", "body": "box", "at": 1}])
    r = run(json.dumps(scene))
    assert not r.solver_match
    assert "missing query" in r.mismatches[0]


def test_gold_is_solved_once_per_example():
    gold_solver = FakeSolver()
    gold = GoldCache(lambda ex: GOLD_SCENE, gold_solver)
    for _ in range(3):
        evaluate_item(ITEM, json.dumps(good_scene()), schema=SCHEMA, gold=gold, solver=FakeSolver())
    assert gold_solver.calls == 1


def test_summarize_per_example_and_overall():
    ok = run(json.dumps(good_scene()))
    bad = run("nope")
    other = run(json.dumps(good_scene()))
    other.example = "other"
    s = summarize([ok, bad, other])
    assert s["toy"]["n"] == 2 and s["toy"]["valid_json_count"] == 1
    assert s["toy"]["valid_json"] == 0.5
    assert s["other"]["solver_match"] == 1.0
    assert s["overall"]["n"] == 3 and s["overall"]["solver_match_count"] == 2


@pytest.mark.solver
def test_real_solver_scores_every_gold_authoring_scene_perfectly():
    from parser_model.solve import solve_scene

    schema = paths.load_schema()
    gold = GoldCache(lambda ex: json.loads(paths.gold_scene_path(ex).read_text()), solve_scene)
    seed = paths.load_seed(paths.model_dir() / "data" / "seed.jsonl")
    n = 0
    for item in seed:
        twin = paths.authoring_path(item["example"])
        if not twin.exists():
            continue
        r = evaluate_item(item, twin.read_text(), schema=schema, gold=gold, solver=solve_scene)
        assert r.failures == [], (item["id"], r.failures)
        n += 1
    assert n == 21


@pytest.mark.solver
def test_real_solver_exit_codes():
    from parser_model.solve import solve_scene

    ok = solve_scene(paths.authoring_path("projectile"))
    assert ok.exit_code == 0 and set(ok.answers) == {"p", "v"} and ok.warnings
    bad = solve_scene({"version": 1.1})
    assert bad.exit_code == 1 and bad.issues


def test_items_with_their_own_gold_scene():
    item = {**ITEM, "id": "syn/x", "example": "incline", "scene": GOLD_SCENE}
    gold = GoldCache(
        lambda ex: pytest.fail("must not load examples/ for generated items"), FakeSolver()
    )
    r = evaluate_item(item, json.dumps(good_scene()), schema=SCHEMA, gold=gold, solver=FakeSolver())
    assert r.solver_match
