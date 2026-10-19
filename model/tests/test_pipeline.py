import json
from types import SimpleNamespace

from parser_model.pipeline import answer_question, check_output, describe
from parser_model.solve import SolveResult

SCHEMA = {"type": "object", "properties": {"version": {"const": 1.1}}, "required": ["version"]}


def scene(title="find: velocity", queries=None):
    return {
        "version": 1.1,
        "title": title,
        "bodies": [{"id": "b"}],
        "queries": queries or [{"id": "v", "ask": "velocity", "body": "b", "at": 8}],
    }


def solver(s):
    return SolveResult(
        exit_code=0,
        answers={q["id"]: [44.0, 0.0, 0.0] for q in s["queries"]},
        warnings=["bodies[0].mass: no mass: using 1 kg", "duration: no duration given"],
    )


class FakeClient:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.config = SimpleNamespace(temperature=0.0)
        self.seen = []

    def complete(self, messages):
        self.seen.append(self.config.temperature)
        return SimpleNamespace(raw=self.outputs.pop(0))


def run(outputs, **kw):
    return answer_question(FakeClient(outputs), "q", solver=solver, schema=SCHEMA, **kw)


def test_a_valid_scene_is_answered_and_explained_with_its_assumptions():
    r = run([json.dumps(scene())])
    assert r.status == "answered" and len(r.attempts) == 1
    assert r.answers[0].text == "Velocity at t = 8 s: 44 m/s (components [44, 0, 0] m/s)"
    assert r.assumptions == ["bodies[0].mass: no mass: using 1 kg"]
    assert "Assumptions made:" in r.explanation and "no duration" not in r.explanation


def test_refusals_become_unsupported_or_not_physics():
    r = run([json.dumps({"unsupported": "circular motion"})])
    assert r.status == "unsupported" and r.reason == "circular motion"
    r = run([json.dumps({"unsupported": "not a mechanics problem"})])
    assert r.status == "not_physics"


def test_unknown_asks_in_the_find_line_turn_a_scene_into_a_refusal():
    r = run([json.dumps(scene(title="find: velocity, separation"))])
    assert r.status == "unsupported" and "separation" in r.reason


def test_bad_outputs_are_retried_with_sampling_until_one_is_valid():
    short = scene(title="find: velocity, position")  # declares two, queries one
    client = FakeClient(["not json", json.dumps(short), json.dumps(scene())])
    r = answer_question(client, "q", solver=solver, schema=SCHEMA, retries=3, retry_temperature=0.9)
    assert r.status == "answered" and [a["status"] for a in r.attempts] == [
        "invalid",
        "invalid",
        "scene",
    ]
    assert client.seen == [0.0, 0.9, 0.9] and client.config.temperature == 0.0


def test_failure_after_all_retries_is_reported_not_raised():
    r = run(["x", "y", "z"], retries=2)
    assert r.status == "failed" and r.reason and "rephras" in r.explanation


def test_solver_errors_count_as_invalid():
    bad = lambda s: SolveResult(exit_code=1, issues=[{"path": "bodies", "message": "nope"}])  # noqa: E731
    checked = check_output(json.dumps(scene()), SCHEMA, bad)
    assert checked.kind == "invalid" and checked.note.startswith("solver:")


def test_describe_scalars_vectors_and_events():
    assert describe({"ask": "time", "until": {"event": "land"}}, 4.4)[1] == "Time of flight: 4.4 s"
    assert describe({"ask": "max_height", "body": "b"}, 56.47)[1] == "Maximum height: 56.47 m"
    text = describe({"ask": "velocity", "body": "b", "at": {"event": "land"}}, [0.0, -33.285, 0.0])[
        1
    ]
    assert text.startswith("Impact velocity: 33.28 m/s")
    assert "could not compute" in describe({"ask": "range", "body": "b"}, None)[1]
