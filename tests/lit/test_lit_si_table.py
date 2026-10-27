"""The table of DOIs cited by the parameter table is generated from data/params.yaml and data/evidence_table.csv."""
from biomin_screen import _util
from biomin_screen.literature import evidence as E
from biomin_screen.literature import params as P
from biomin_screen.literature import si_table as S

ROOT = _util.repo_root()


def test_committed_table_is_current():
    generated = S.generate(ROOT)
    for name, text in generated.items():
        path = ROOT / S.OUT / name
        assert path.exists(), name
        assert path.read_text(encoding="utf-8") == text, "%s is stale: run python -m biomin_screen.literature.si_table" % name


def test_every_doi_is_an_evidence_doi_and_is_listed_once():
    listed = S.generate(ROOT)["params_table_dois.csv"].split()
    assert listed[0] == "doi" and len(listed[1:]) == len(set(listed[1:]))
    dois = {r["doi"].lower() for r in E.read_csv(ROOT / P.TABLE)[1]}
    assert listed[1:] and set(listed[1:]) <= dois


def test_every_source_row_of_a_key_is_cited():
    p = P.load_params(ROOT / P.PARAMS, ROOT)
    rows = {r["row_id"]: r for r in E.read_csv(ROOT / P.TABLE)[1]}
    cited = set(S.generate(ROOT)["params_table_dois.csv"].split()[1:])
    for key, e in p.entries.items():
        assert set(S.dois_of(e, rows)) <= cited, key


def test_check_mode_reports_a_stale_file(tmp_path, capsys):
    assert S.main(["--out", str(tmp_path), "--check"]) == 1
    assert "stale" in capsys.readouterr().out
    assert S.main(["--out", str(tmp_path)]) == 0
    assert S.main(["--out", str(tmp_path), "--check"]) == 0
