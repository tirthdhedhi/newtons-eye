from parser_model.metrics import compare_answers, query_signature, signatures, values_close


def scene(*queries, bodies=None, connections=None):
    return {
        "bodies": bodies if bodies is not None else [{"id": "block", "mass": "5 kg"}],
        "connections": connections or [],
        "queries": list(queries),
    }


def test_signature_ignores_query_id():
    a = {"id": "a", "ask": "acceleration", "body": "block", "at": 1}
    b = {"id": "zzz", "ask": "acceleration", "body": "block", "at": 1}
    assert query_signature(a) == query_signature(b)


def test_signature_distinguishes_every_field():
    base = {"ask": "force", "force": "friction", "body": "block", "at": 1}
    variants = [
        {**base, "ask": "acceleration"},
        {**base, "force": "normal"},
        {**base, "body": "other"},
        {**base, "at": 2},
        {**base, "until": {"event": "stop"}},
        {**base, "connection": "rope"},
        {**base, "from": 0},
    ]
    sigs = {query_signature(v) for v in variants}
    assert query_signature(base) not in sigs
    assert len(sigs) == len(variants)


def test_signature_normalises_units_and_numbers():
    a = {"ask": "work", "body": "b", "from": 0, "to": "6 s"}
    b = {"ask": "work", "body": "b", "from": 0.0, "to": 6}
    assert query_signature(a) == query_signature(b)
    c = {"ask": "time", "body": "b", "at": "2000 ms"}
    d = {"ask": "time", "body": "b", "at": 2}
    assert query_signature(c) == query_signature(d)


def test_until_dicts_compare_by_content():
    a = {"ask": "time", "body": "b", "until": {"event": "stop"}}
    b = {"ask": "time", "body": "b", "until": {"event": "stop"}}
    c = {"ask": "time", "body": "b", "until": {"event": "edge"}}
    assert query_signature(a) == query_signature(b) != query_signature(c)


def test_bodies_are_named_by_mass_not_id():
    gold = scene({"id": "a", "ask": "acceleration", "body": "block", "at": 1})
    model = scene(
        {"id": "q1", "ask": "acceleration", "body": "box", "at": 1},
        bodies=[{"id": "box", "mass": 5}],
    )
    assert list(signatures(gold).values()) == list(signatures(model).values())


def test_connections_are_named_by_the_masses_they_join():
    bodies = [{"id": "m1", "mass": "3 kg"}, {"id": "m2", "mass": "5 kg"}]
    gold = scene(
        {"id": "T", "ask": "force", "force": "tension", "connection": "rope", "at": 0.2},
        bodies=bodies,
        connections=[{"id": "rope", "a": "m1", "b": "m2"}],
    )
    model = scene(
        {"id": "x", "ask": "force", "force": "tension", "connection": "string", "at": 0.2},
        bodies=[{"id": "p", "mass": 5}, {"id": "q", "mass": 3}],
        connections=[{"id": "string", "a": "p", "b": "q"}],
    )
    assert list(signatures(gold).values()) == list(signatures(model).values())


def test_compare_matches_by_signature_not_id():
    gold = scene(
        {"id": "a", "ask": "acceleration", "body": "block", "at": 1},
        {"id": "N", "ask": "force", "force": "normal", "body": "block", "at": 1},
    )
    model = scene(
        {"id": "N", "ask": "acceleration", "body": "block", "at": 1},  # ids swapped
        {"id": "a", "ask": "force", "force": "normal", "body": "block", "at": 1},
    )
    gold_answers = {"a": [1.0, 0.0, 0.0], "N": 42.0}
    model_answers = {"N": [1.0, 0.0, 0.0], "a": 42.0}
    assert compare_answers(gold, gold_answers, model, model_answers) == []


def test_compare_reports_missing_and_wrong():
    gold = scene(
        {"id": "a", "ask": "acceleration", "body": "block", "at": 1},
        {"id": "N", "ask": "force", "force": "normal", "body": "block", "at": 1},
    )
    model = scene({"id": "a", "ask": "acceleration", "body": "block", "at": 1})
    problems = compare_answers(gold, {"a": 2.0, "N": 3.0}, model, {"a": 2.5})
    assert len(problems) == 2
    assert any("missing" in p for p in problems)
    assert any("got 2.5" in p for p in problems)


def test_tolerance_is_relative_1e_3():
    assert values_close(100.0, 100.09)
    assert not values_close(100.0, 100.2)
    assert values_close([1.0, 0.0, 0.0], [1.0005, 1e-12, 0.0])
    assert not values_close([1.0, 0.0], [1.0, 0.0, 0.0])
    assert not values_close(None, 1.0)
    assert not values_close(1.0, [1.0])


def test_max_height_signature_defaults_to_ground_and_separates_start():
    ground = query_signature({"ask": "max_height", "body": "b"})
    assert ground == query_signature({"ask": "max_height", "body": "b", "above": "ground"})
    assert ground != query_signature({"ask": "max_height", "body": "b", "above": "start"})


def test_event_times_and_landing_queries_are_part_of_the_signature():
    land = {"ask": "velocity", "body": "b", "at": {"event": "land"}}
    assert query_signature(land) != query_signature({"ask": "velocity", "body": "b", "at": 1})
    assert query_signature(land) == query_signature(dict(land))
    until_land = {"ask": "time", "body": "b", "until": {"event": "land"}}
    assert query_signature(until_land) != query_signature(
        {"ask": "time", "body": "b", "until": {"event": "stop"}}
    )


def test_missing_time_means_zero():
    base = {"ask": "acceleration", "body": "b"}
    assert query_signature(base) == query_signature({**base, "at": 0})
    assert query_signature(base) != query_signature({**base, "at": 1})


def test_bodies_without_a_mass_are_matched_by_position_not_by_id():
    gold = scene({"id": "v", "ask": "velocity", "body": "car", "at": 8}, bodies=[{"id": "car"}])
    model = scene({"id": "x", "ask": "velocity", "body": "body", "at": 8}, bodies=[{"id": "body"}])
    assert list(signatures(gold).values()) == list(signatures(model).values())
    two = [{"id": "a"}, {"id": "b"}]
    q = lambda body: {"id": "v", "ask": "velocity", "body": body, "at": 1}  # noqa: E731
    first = scene(q("a"), bodies=two)
    swapped = scene(q("b"), bodies=two)
    assert list(signatures(first).values()) != list(signatures(swapped).values())
