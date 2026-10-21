from parser_model.asks import ask_label, asks_complete, declared_asks, title_for, with_title


def scene(queries, title=None):
    out = {"version": 1.1, "bodies": [{"id": "b"}], "queries": queries}
    return {**out, "title": title} if title else out


Q = [
    {"id": "v", "ask": "velocity", "body": "b", "at": 8},
    {"id": "T", "ask": "time", "until": {"event": "land"}, "body": "b"},
    {"id": "I", "ask": "velocity", "body": "b", "at": {"event": "land"}},
    {"id": "N", "ask": "force", "force": "normal", "body": "b"},
    {"id": "H", "ask": "max_height", "body": "b"},
]


def test_labels_are_canonical():
    assert [ask_label(q) for q in Q] == [
        "velocity",
        "time of flight",
        "impact velocity",
        "normal force",
        "maximum height",
    ]


def test_title_goes_right_after_version_and_roundtrips():
    s = with_title(scene(Q[:2]))
    assert list(s)[:2] == ["version", "title"]
    assert s["title"] == "find: velocity, time of flight" == title_for(scene(Q[:2]))
    assert declared_asks(s) == ["velocity", "time of flight"]


def test_incomplete_scenes_are_detected():
    declared_three = scene(Q[:2], title="find: velocity, displacement, time of flight")
    assert not asks_complete(declared_three)
    assert asks_complete(scene(Q[:3], title="find: a, b, c"))
    assert asks_complete(scene(Q[:1]))  # no title, nothing to check
    assert asks_complete(scene(Q[:1], title="a plain title"))


def test_vote_ignores_candidates_that_declared_more_than_they_wrote():
    import json

    from parser_model.solve import SolveResult
    from parser_model.vote import candidate_key

    schema = {"type": "object"}
    ok = lambda s: SolveResult(exit_code=0, answers={q["id"]: 1.0 for q in s["queries"]})  # noqa: E731
    short = json.dumps(scene(Q[:1], title="find: velocity, displacement"))
    full = json.dumps(scene(Q[:2], title="find: velocity, displacement"))
    assert candidate_key(short, schema, ok) is None
    assert candidate_key(full, schema, ok) is not None


def test_unknown_asks_catch_things_the_solver_cannot_compute():
    from parser_model.asks import KNOWN_ASKS, unknown_asks

    assert all(ask_label(q).lower() in KNOWN_ASKS for q in Q)
    refuses = scene(Q[:2], title="find: time of flight, separation, equilibrium")
    assert unknown_asks(refuses) == ["separation", "equilibrium"]
    assert unknown_asks(scene(Q[:2], title="find: velocity, time of flight")) == []
    assert unknown_asks(scene(Q[:1])) == []  # no find line, nothing to judge
