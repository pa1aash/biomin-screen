"""The spec has a source for every value, the style is generated from it, and the palette holds the Okabe-Ito colours."""
import importlib.util
import re

import numpy as np
import pytest
import yaml
from figs_helpers import REPO

STYLE = REPO / "figures" / "style"


def _load(name):
    spec = importlib.util.spec_from_file_location("figs_" + name, STYLE / (name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def spec():
    return yaml.safe_load((STYLE / "rsc_spec.yaml").read_text())


@pytest.fixture(scope="module")
def palette():
    return yaml.safe_load((STYLE / "palette.yaml").read_text())


def test_every_spec_value_has_source_locator_and_quote(spec):
    for key, v in spec["values"].items():
        assert v.get("value") is not None, key
        assert v["source"] in spec["sources"], key
        assert v.get("locator", "").strip(), key
        assert v.get("quote", "").strip(), key


def test_sources_name_a_document(spec):
    for sid, s in spec["sources"].items():
        assert s["title"] and s["url"].startswith("https://"), sid


def test_outstanding_values_record_the_search(spec):
    assert spec["outstanding"]
    for key, v in spec["outstanding"].items():
        assert v["searched"] and v["result"].strip(), key


def test_applied_values_trace_to_a_value_or_a_house_reason(spec):
    for key, a in spec["applied"].items():
        if a.get("house"):
            assert a.get("reason", "").strip(), key
        else:
            ref = a["from"]
            assert ref.startswith("values.") and ref.split(".", 1)[1] in spec["values"], key
            assert a.get("rule", "").strip(), key


def test_style_is_generated_and_current():
    mod = _load("build_style")
    assert (STYLE / "rsc.mplstyle").read_text() == mod.build()


def test_every_style_line_traces_to_the_spec(spec, palette):
    for line in (STYLE / "rsc.mplstyle").read_text().splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        assert "#" in line, line
        trace = line.split("#", 1)[1].strip()
        m = re.match(r"(applied|palette)\.([A-Za-z_.]+)", trace)
        assert m, line
        if m.group(1) == "applied":
            assert m.group(2).split(".")[0] in spec["applied"], line
        else:
            node = palette
            for part in m.group(2).split("."):
                node = node[part]


def test_style_values_match_spec(spec):
    import matplotlib
    rc = matplotlib.rc_params_from_file(str(STYLE / "rsc.mplstyle"), use_default_template=False)
    ap = spec["applied"]
    assert rc["font.size"] == ap["font_size"]["value"]
    assert rc["axes.linewidth"] == ap["line_width_min"]["value"]
    assert rc["savefig.dpi"] == ap["raster_dpi"]["value"]
    assert rc["font.sans-serif"][0] == ap["font_family"]["value"]
    assert rc["pdf.fonttype"] == 42


def test_widths_match_rsc_columns(spec):
    for kind in ("single", "double"):
        cm = spec["values"]["width_%s_column" % kind]["value"]
        assert abs(spec["applied"]["width_%s_in" % kind]["value"] - cm / 2.54) < 1e-4


def test_palette_holds_the_okabe_ito_colours_and_the_cycle(palette):
    oi = palette["categorical"]["okabe_ito"]
    assert len(oi) == 9 and palette["delta_e_min"] > 0
    for name, c in oi.items():
        assert re.fullmatch(r"#[0-9A-F]{6}", c["hex"]), name
        assert np.allclose([int(c["hex"][i:i + 2], 16) / 255 for i in (1, 3, 5)], c["srgb"], atol=1e-3), name
    for name in palette["categorical"]["cycle"]:
        assert name in oi


def test_regime_fills_clear_the_palette_threshold():
    from biomin_screen.figures import colours, regimes
    fills = regimes.fills(REPO)
    assert colours.min_delta_e(list(fills.values())) >= float(yaml.safe_load((STYLE / "palette.yaml").read_text())["delta_e_min"])


# ------------------------------------------------------------------ font fallback

def _only(monkeypatch, installed):
    from biomin_screen.figures import style
    monkeypatch.setattr(style, "_find", lambda name: ("/fonts/%s.ttf" % name) if name in installed else None)


def test_font_chain_ends_with_the_always_present_face():
    from biomin_screen.figures import style
    chain = style.font_chain(REPO)
    assert chain == ["Helvetica", "Liberation Sans", "DejaVu Sans"] and "Arial" not in chain


@pytest.mark.parametrize("installed, family, rank", [
    ({"Helvetica", "Liberation Sans", "DejaVu Sans"}, "Helvetica", 0),
    ({"Liberation Sans", "DejaVu Sans"}, "Liberation Sans", 1),
    ({"DejaVu Sans"}, "DejaVu Sans", 2),
])
def test_font_takes_the_first_installed_face(monkeypatch, installed, family, rank):
    from biomin_screen.figures import style
    _only(monkeypatch, installed)
    f = style.font(REPO)
    assert (f["family"], f["rank"]) == (family, rank)


def test_no_installed_face_is_an_error_not_a_silent_default(monkeypatch):
    from biomin_screen.figures import style
    _only(monkeypatch, set())
    with pytest.raises(style.FontError, match="DejaVu Sans"):
        style.font(REPO)


def test_dejavu_sans_is_always_found():
    from biomin_screen.figures import style
    assert style._find("DejaVu Sans")


def test_use_pins_the_chosen_face_alone():
    from biomin_screen.figures import style
    plt = style.use(REPO)
    assert list(plt.rcParams["font.sans-serif"]) == [style.font(REPO)["family"]]


def test_find_returns_none_for_a_missing_face():
    from biomin_screen.figures import style
    assert style._find("No Such Face Anywhere") is None
