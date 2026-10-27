"""The inputs of the figures conform to their schemas, and the schemas match the documented record."""
import json
import re

import pytest
from figs_helpers import REPO

from biomin_screen.figures import build, paths, schema


def _mods():
    return [build.load_template(p) for p in build.discover(REPO)]


def test_the_release_set_is_the_seven_data_figures():
    assert {m.FIGURE["id"]: m.FIGURE["name"] for m in _mods()} == {
        "fig4": "retrodiction", "fig7": "carbonate_dissolution", "fig10": "formation_benchmark",
        "fig11": "al_window", "fig14": "precision_map", "fig15": "regime_map", "fig17": "k2_vs_k1"}


@pytest.mark.parametrize("fid", ["fig4", "fig7", "fig10", "fig11", "fig14", "fig15", "fig17"])
def test_input_files_exist_and_conform_to_the_schema(fid):
    mod = build.load_template(paths(REPO)["src"] / (fid + ".py"))
    assert build.load_input(REPO, mod) is not None  # raises FigureError on a schema violation
    for ref in mod.FIGURE.get("aux", {}).values():
        assert (REPO / ref).is_file(), ref


def test_every_figure_is_listed_in_the_readme_table():
    text = (REPO / "figures/README.md").read_text()
    for m in _mods():
        assert "| %s | `%s` |" % (m.FIGURE["id"], m.FIGURE["name"]) in text
        for ref in [m.FIGURE["input"]] + list(m.FIGURE.get("aux", {}).values()):
            assert ref.rsplit("/", 1)[-1] in text, (m.FIGURE["id"], ref)


def _example_record():
    """The JSON example of SCHEMA.md section 5."""
    text = (REPO / "data/retrodiction/SCHEMA.md").read_text()
    block = re.search(r"## 5\. Result record.*?```json\n(.*?)```", text, re.S).group(1)
    return json.loads(block)


def test_retro_transcription_has_exactly_the_documented_fields():
    ex = _example_record()
    sch, _ = schema.resolve("figures/src/schemas/retro_results.schema.json", REPO)
    assert set(sch["properties"]) == set(ex)
    assert set(sch["required"]) == set(ex)
    case = sch["$defs"]["case"]
    assert set(case["properties"]) == set(ex["cases"][0]) == set(case["required"])
    assert set(sch["properties"]["summary"]["properties"]) == set(ex["summary"])
    assert set(sch["properties"]["provenance"]["properties"]) == set(ex["provenance"])
    assert set(sch["$defs"]["interval"]["properties"]) == set(ex["cases"][0]["delta"])
    assert set(case["properties"]["verdict"]["enum"]) == set(ex["cases"][0]["verdict"].split(" | "))


def test_retro_transcription_terminations_follow_the_documented_table():
    text = (REPO / "data/retrodiction/SCHEMA.md").read_text()
    row = next(line for line in text.splitlines() if line.startswith("| `termination`"))
    documented = set(re.findall(r"`([a-z]+)`", row.split("|")[2]))
    sch, _ = schema.resolve("figures/src/schemas/retro_results.schema.json", REPO)
    assert set(sch["$defs"]["case"]["properties"]["termination"]["enum"]) == documented


def test_screen_schema_rejects_a_scheme_row_without_status():
    sch, _ = schema.resolve("configs/results_schema.json", REPO)
    doc = json.loads((REPO / "results/screen/table_r2/summary.json").read_text())
    assert schema.validate(doc, sch) == []
    del doc["claims"]["C5"]["tests"]["C5c_ox"]["scheme_table"][0]["status"]
    assert schema.validate(doc, sch)


def test_symbol_titles_come_from_the_register():
    import yaml
    from biomin_screen.figures.symbols import axis_title, symbol
    reg = {s["id"]: s for s in yaml.safe_load((REPO / "data/symbols.yaml").read_text())["symbols"]}
    assert symbol("Omega_bulk", REPO) == "$%s$" % reg["Omega_bulk"]["latex"]
    assert axis_title("theta", REPO, unit="°").endswith("(°)")
    with pytest.raises(KeyError):
        symbol("no_such_symbol", REPO)


def test_csv_inputs_are_read_with_comment_lines_skipped():
    doc = build.parse_csv("# a comment\na,b\n1,2\n")
    assert doc == {"columns": ["a", "b"], "rows": [{"a": "1", "b": "2"}]}


def test_a_missing_input_is_refused(tmp_path):
    with pytest.raises(build.FigureError, match="missing"):
        build.read(tmp_path / "none.json")
