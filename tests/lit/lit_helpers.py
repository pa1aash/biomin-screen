from biomin_screen.literature import evidence as E


def good_row(**kw):
    r = {
        "row_id": "TC-001", "thread": "T-C", "doi": "10.1021/example.123", "locator": "p. 4, Table 2",
        "quantity": "ksp_calcite", "symbol": "log10 Ksp", "value": "-8.48", "unit": "1",
        "range_or_uncertainty": "±0.02", "conditions": "T=298.15 K; pH=n.s.; I->0; water; calcite",
        "method": "experiment: solubility titration", "grade": "A", "extraction_route": "full text",
        "retrieved_at": "2026-10-16T09:00:00Z", "contrary": "n", "retro_candidate": "n",
        "notes": "infinite-dilution value from the regression",
    }
    r.update(kw)
    return r


__all__ = ["E", "good_row"]
