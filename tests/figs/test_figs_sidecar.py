"""The numeric sidecar and the check of the shipped figures."""
import json

from figs_helpers import REPO, check, clean_figure

from biomin_screen.figures import build, sidecar


def test_sidecar_rounds_to_six_significant_digits():
    fig, _ax = clean_figure()
    doc = sidecar.series(fig, {"id": "x", "name": "x", "inputs": []})
    assert doc["axes"][0]["artists"][0]["y"] == [0.0, 1.0, 4.0]
    assert sidecar._num(1.23456789) == 1.23457


def test_differences_use_a_relative_tolerance():
    assert sidecar.differences({"a": [1.0, 2.0]}, {"a": [1.0 + 1e-7, 2.0]}) == []
    assert sidecar.differences({"a": [1.0]}, {"a": [1.0 + 1e-5]})
    assert sidecar.differences({"a": [1.0]}, {"a": [1.0, 2.0]})
    assert sidecar.differences({"a": "x"}, {"a": "y"})


def test_dumps_is_valid_json():
    fig, _ax = clean_figure()
    doc = sidecar.series(fig, {"id": "x", "name": "x", "inputs": ["a"]})
    loaded = json.loads(sidecar.dumps(doc))
    assert loaded["inputs"] == ["a"]
    assert loaded["axes"][0]["artists"] == doc["axes"][0]["artists"]
    assert loaded["axes"][0]["frame"]["xlim"] == doc["axes"][0]["xlim"]
    assert not check(fig)


def test_every_figure_ships_pdf_png_and_sidecar():
    for p in build.discover(REPO):
        name = build.load_template(p).FIGURE["name"]
        for ext in (".pdf", ".png", ".json"):
            assert (REPO / "figures" / (name + ext)).is_file(), name + ext


def test_the_shipped_sidecar_of_the_smallest_figure_is_reproduced(tmp_path):
    problems = build.check(REPO, only=["al_window"], log=lambda *_: None)
    assert problems == []
