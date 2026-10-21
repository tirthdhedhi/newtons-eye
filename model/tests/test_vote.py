import json
from types import SimpleNamespace

from parser_model.solve import SolveResult
from parser_model.vote import candidate_key, choose

SCHEMA = {"type": "object", "properties": {"version": {"const": 1.1}}, "required": ["version"]}


def scene(qs):
    return json.dumps(
        {
            "version": 1.1,
            "bodies": [{"id": "b", "mass": "1 kg"}],
            "queries": [{"id": q, "ask": "acceleration", "body": "b", "at": t} for q, t in qs],
        }
    )


def solver(s):
    answers = {q["id"]: [q["at"], 0.0, 0.0] for q in s["queries"]}
    return SolveResult(exit_code=0, answers=answers)


class FakeClient:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.config = SimpleNamespace(temperature=0.0)
        self.temperatures = []

    def complete(self, messages):
        self.temperatures.append(self.config.temperature)
        return SimpleNamespace(raw=self.outputs.pop(0))


def test_majority_of_valid_candidates_wins_and_ids_do_not_matter():
    good_a, good_b = scene([("a", 1), ("v", 2)]), scene([("x", 1), ("y", 2)])
    dropped = scene([("a", 1)])  # lost a query
    client = FakeClient([dropped, good_a, "not json", good_b, dropped, good_a])
    raw, info = choose(client, [], k=5, temperature=0.7, schema=SCHEMA, solver=solver)
    assert raw in (good_a, good_b) and info["chose"].startswith("majority 3/")
    assert client.temperatures == [0.0] + [0.7] * 5 and client.config.temperature == 0.0


def test_greedy_wins_ties_and_is_the_fallback():
    one, two = scene([("a", 1)]), scene([("a", 2)])
    raw, _ = choose(FakeClient([one, two]), [], k=1, temperature=0.7, schema=SCHEMA, solver=solver)
    assert raw == one
    raw, info = choose(
        FakeClient(["x", "y"]), [], k=1, temperature=0.7, schema=SCHEMA, solver=solver
    )
    assert raw == "x" and "nothing valid" in info["chose"]


def test_refusals_vote_together_and_invalid_scenes_do_not_count():
    refuse = json.dumps({"unsupported": "circular motion"})
    assert candidate_key(refuse, SCHEMA, solver) == "REFUSE"
    assert candidate_key(json.dumps({"nope": 1}), SCHEMA, solver) is None
    bad = lambda s: SolveResult(exit_code=1)  # noqa: E731
    assert candidate_key(scene([("a", 1)]), SCHEMA, bad) is None
    client = FakeClient([scene([("a", 1)]), refuse, refuse])
    raw, _ = choose(client, [], k=2, temperature=0.7, schema=SCHEMA, solver=solver)
    assert raw == refuse
