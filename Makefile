# biomin-screen: reproduce the numbers, tables and data figures of the paper from the sourced inputs.
# The repository's own source is used, never an installed copy of the package.

SHELL := /bin/sh
ROOT := $(CURDIR)
VENV := $(ROOT)/.venv
PY := $(if $(wildcard $(VENV)/bin/python),$(VENV)/bin/python,python3)
export PYTHONPATH := $(ROOT)/src
export BIOMIN_SCREEN_ROOT := $(ROOT)
export PYTHONHASHSEED := 0
export OMP_NUM_THREADS := 1
export OPENBLAS_NUM_THREADS := 1

.PHONY: help env unpack test check numbers screen screen-quick tables figures all clean

help:
	@echo "make env           create .venv from the pinned requirements (needs uv or pip and network; once)"
	@echo "make test          run the test suite (no network; about 2 minutes)"
	@echo "make check         regenerate the stored outputs in work/ and compare them with the shipped ones (about 6 minutes)"
	@echo "make numbers       print the headline quantities of the paper with their intervals (seconds)"
	@echo "make tables        rebuild the tables in results/tables/ from the stored outputs (seconds)"
	@echo "make figures       rebuild the data figures in figures/ (under 10 seconds)"
	@echo "make screen        rebuild the omitted per-cell documents, then rerun every stage and the long production runs and compare"
	@echo "                   (about 20 minutes, single core, peak 1.9 GB; needs 8 GB of memory)"
	@echo "make screen-quick  the omitted per-cell documents and the two production runs with 8192 samples per state and no sensitivity analysis,"
	@echo "                   in work/quick/ (about 2 minutes; not identical to the shipped summaries)"
	@echo "make all           test, check, tables, figures, numbers"
	@echo "make clean         remove work/, caches and build products"
	@echo "Runtime and inputs of each target: see README.md."

env:
	@if command -v uv >/dev/null 2>&1; then \
	  uv venv --python 3.12 $(VENV) && uv pip install --python $(VENV)/bin/python -r requirements.txt; \
	else \
	  python3.12 -m venv $(VENV) && $(VENV)/bin/pip install -r requirements.txt; \
	fi

# the large result files are shipped gzip-compressed; this writes the plain copies that are missing
unpack:
	@$(PY) -m biomin_screen.archive unpack

test: unpack
	$(PY) -m pytest -q

check: unpack
	$(PY) scripts/check.py

tables: unpack
	$(PY) -m biomin_screen tables regime
	$(PY) -m biomin_screen tables breakeven
	$(PY) -m biomin_screen tables inputs

figures: unpack
	$(PY) -m biomin_screen figures

numbers: unpack
	$(PY) scripts/numbers.py

screen: unpack
	$(PY) scripts/screen.py

screen-quick: unpack
	$(PY) scripts/screen.py --quick

all: test check tables figures numbers

clean:
	rm -rf work .pytest_cache .hypothesis build dist *.egg-info
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
