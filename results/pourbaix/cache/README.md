# Cached thermodynamic data

Raw responses read by `src/biomin_screen/pourbaix/`. Every diagram, window and ladder reads these files and
nothing else; nothing here needs a network connection or an API key to use. Attribution and licences are in
`NOTICE.md` and `../../../THIRD_PARTY.md`.

| File | Source | Request |
|---|---|---|
| `mp_entries_slurry_Al-C-Ca-H-Na-O.json` | Materials Project, thermodynamic entries | `get_entries_in_chemsys`, `thermo_types = [GGA_GGA+U]`, MP2020-compatible entries |
| `mp_entries_cell_<chemsys>.json` | Materials Project, thermodynamic entries | the same request, one file per element system of the cell window (the sinks of LiClO4, LiBOB and LiPCP among them) |
| `mp_ion_reference_data.json` | Materials Project, MPContribs project `ion_ref_data` | `get_ion_reference_data`, all records |
| `janaf_<species>.json` | NIST-JANAF Thermochemical Tables | HTTP GET of the table text (the URL is stored in each file) |
| `nbs1982_ocr.json` | NBS tables (Wagman et al. 1982) | the scanned PDF, rendered at 200 dpi and read by OCR; pages 136, 137 and 276 |
| `manifest.json` | this cache | database version, client versions, the request, retrieval time and sha256 of each file |

Each data file holds `request`, `retrieved_utc` and the raw `response` (or `text`). Each Materials Project file
also holds `mp_database_version` and `client_versions`. Entry dictionaries are stored as returned, except that
the keys of each entry's free-form `data` field are turned into strings so that the file is valid JSON. The
slurry system includes Na because the reference solid of the carbonate ions in `ion_ref_data` is Na2CO3;
Na-bearing solids are removed from the diagram, as the Materials Project client does.

The cache answers two thermodynamic questions:

1. Which Al-, Ca- and C-bearing species are at equilibrium on the aqueous (pH, E vs SHE) plane?
2. At what potential against Li+/Li does CaCO3, or an Al oxide, take up Li (reduction) or release O2 (oxidation)?

Neither answer is a rate. A stable domain or a window is a thermodynamic proxy for the dissolution and corrosion
questions of the screen, not a statement about them.
