import json
import math

import pytest

from parser_model import paths
from parser_model.grounding import (
    check_grounding,
    extract_quantities,
    parse_quantity_string,
    scene_numbers,
)


def si(question: str) -> dict[str, float]:
    return {q.text: q.value for q in extract_quantities(question)}


@pytest.mark.parametrize(
    ("text", "value", "dim"),
    [
        ("5 kg", 5.0, "mass"),
        ("500 g", 0.5, "mass"),
        ("30 cm", 0.3, "length"),
        ("2 km", 2000.0, "length"),
        ("72 km/h", 20.0, "speed"),
        ("10 m/s", 10.0, "speed"),
        ("90 deg", math.pi / 2, "angle"),
        ("30°", math.pi / 6, "angle"),
        ("100 N/m", 100.0, "stiffness"),
        ("2 min", 120.0, "time"),
        ("50 N", 50.0, "force"),
        ("9.8 m/s^2", 9.8, "accel"),
    ],
)
def test_quantity_strings_convert_to_si(text, value, dim):
    got, got_dim = parse_quantity_string(text)
    assert got == pytest.approx(value)
    assert got_dim == dim


def test_non_quantity_strings_are_ignored():
    assert parse_quantity_string("top") is None
    assert parse_quantity_string("block") is None


def test_extracts_units_and_bare_numbers():
    q = si("A 500 g ball at 72 km/h on a 30 degrees ramp, mu_s = 0.4 and mu_k = 0.3, k = 20 N/cm")
    assert q["500 g"] == pytest.approx(0.5)
    assert q["72 km/h"] == pytest.approx(20)
    assert q["30 degrees"] == pytest.approx(math.pi / 6)
    assert q["20 N/cm"] == pytest.approx(2000)
    assert q["0.4"] == 0.4
    assert q["0.3"] == 0.3


def test_number_words():
    q = si("One second in, and half a second later")
    assert q["One second"] == 1.0
    assert q["half a second"] == 0.5


def test_unit_does_not_swallow_following_word():
    assert si("5 meters per second")["5 meters"] == 5.0
    assert "5 m" not in si("5 mph")  # mph is its own unit, not metres


def test_scene_numbers_parse_units_and_skip_version():
    scene = {"version": 1.1, "title": "5 kg", "bodies": [{"mass": "500 g", "v": [1, "2 cm"]}]}
    got = dict(scene_numbers(scene))
    assert got == {
        "bodies[0].mass": pytest.approx(0.5),
        "bodies[0].v[0]": 1.0,
        "bodies[0].v[1]": pytest.approx(0.02),
    }


def test_unit_conversion_grounds_equivalent_scene_values():
    question = "A 500 g block moves at 72 km/h for 2 minutes."
    scene = {"bodies": [{"mass": "0.5 kg", "velocity": "20 m/s"}], "queries": [{"at": "120 s"}]}
    assert check_grounding(question, scene).grounded


def test_unit_mismatch_is_ungrounded():
    result = check_grounding("A 500 g block.", {"bodies": [{"mass": 500}]})
    assert not result.grounded
    assert result.ungrounded[0]["path"] == "bodies[0].mass"


def test_degrees_written_as_bare_number_is_ungrounded():
    # the solver reads a bare angle as radians, so 30 is not 30 degrees
    assert not check_grounding("An incline at 30 degrees.", {"angle": 30}).grounded
    assert check_grounding("An incline at 30 degrees.", {"angle": "30 deg"}).grounded


def test_defaults_gravity_and_zero():
    assert check_grounding("A block.", {"g": 9.81, "offset": 0}).grounded
    assert not check_grounding("A block.", {"g": 10}).grounded


def test_derived_pair_is_allowed():
    q = "A ball moves 10 m/s horizontally and 10 m/s up."
    scene = {"velocity": {"speed": "14.142135623730951 m/s", "angle": "45 deg"}}
    assert check_grounding(q, scene).grounded


def test_sign_is_not_a_given():
    assert check_grounding("Moving at 5 m/s.", {"v": "-5 m/s"}).grounded


def test_invented_value_is_reported():
    result = check_grounding("A 5 kg block.", {"mass": "5 kg", "mu": 0.7})
    assert [u["path"] for u in result.ungrounded] == ["mu"]


def test_every_gold_authoring_scene_is_grounded_in_every_phrasing():
    seed = paths.load_seed(paths.model_dir() / "data" / "seed.jsonl")
    checked = 0
    for item in seed:
        path = paths.authoring_path(item["example"])
        if not path.exists():
            continue
        result = check_grounding(item["question"], json.loads(path.read_text()))
        assert result.grounded, (item["id"], result.ungrounded)
        checked += 1
    assert checked == 21


def test_hyphenated_and_latex_units():
    q = si(
        "a 20-degree incline, a 250-kg safe, \\( t = 2 \\) s, 30^\\circ above, "
        "\\(5\\,\\text{m/s}\\)"
    )
    assert q["20-degree"] == pytest.approx(math.radians(20))
    assert q["250-kg"] == 250
    assert any(v == pytest.approx(math.radians(30)) for v in q.values())
    assert any(v == 5 for v in q.values())
    assert check_grounding("a 20-degree incline", {"angle": "20 deg"}).grounded
    assert check_grounding("a 20-degree incline", {"angle": 0.3490658503988659}).grounded
