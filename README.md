# Patent Analysis Prototype

This repository now contains the first working scaffold for the Fuyao patent analysis project described in the `readme/` folder. The implementation focuses on the documented Phase 1 and Phase 2 requirements first:

- patent ingestion through pdf upload,
- technical feature extraction with evidence traces,
- structured storage in SQLite,
- product design input and feature normalization,
- explainable patent-to-product risk analysis,
- a localhost web UI for browsing, review, and demo runs.

## Why this stack

- `FastAPI`: lightweight Python web framework for local development and later private deployment.
- `Jinja2` templates: simple server-rendered frontend that runs well on localhost and can be hosted behind a private reverse proxy later.
- `SQLite` now: fast, file-based prototype database with a clean path to PostgreSQL later.
- Rule-based extraction and scoring remain available as a fallback path for stability and explainability.
- `OpenRouter` integration is now live for AI-assisted patent feature extraction and design-around suggestions when enabled in local config.

## Project structure

```text
config/                  Editable settings, including OpenRouter configuration
data/                    Demo patents, demo product designs, SQLite database, future live imports
docs/                    Architecture and extension notes
src/patent_analysis/     Application package, CLI, and shared runtime wiring
tests/                   Core service smoke tests
main.py                  Thin launcher that points Python at the src/ package
```

## Local setup

1. Create or reuse your virtual environment.
2. Install dependencies:

```bash
./.venv/bin/pip install -r requirements.txt
```

3. Adjust the local configuration in `config/settings.local.toml`.
4. Start the app:

```bash
./.venv/bin/python main.py
```

Then open [http://127.0.0.1:8000](http://127.0.0.1:8000).

## Commands

```bash
./.venv/bin/python main.py              # run the web app
./.venv/bin/python main.py runserver    # run the web app explicitly
./.venv/bin/python main.py init-db      # create the SQLite schema
./.venv/bin/python main.py seed-demo    # load demo patents and demo designs
./.venv/bin/python main.py import-patents --source dpma_xml
./.venv/bin/python main.py import-ipc-scheme
./.venv/bin/python main.py test-openrouter
./.venv/bin/python main.py test-patent-extraction
./.venv/bin/python main.py reextract-patents
./.venv/bin/python -m unittest discover -s tests
```

## DPMA workflow

The app now supports a simple real-patent import path for downloaded DPMA XML files.

1. Place DPMA patent XML files in `data/dpma_xml/`.
2. Import them into SQLite:

```bash
./.venv/bin/python main.py import-patents --source dpma_xml
```

3. Open the web UI and use:

- `Patents` to filter by free text, extracted feature term, IPC class, source, and feature family
- `Screening` to compare a new patent idea or a saved patent against the stored library
- `Risk Analysis` to compare a product design against a selected patent

## IPC scheme workflow

The current `DE_ExportIPC.xml` file is an official IPC scheme export, not a patent full-text export. The app can import it as a classification reference layer.

```bash
./.venv/bin/python main.py import-ipc-scheme
```

After import:

- `IPC` lets you browse and search the official DPMA IPC hierarchy
- `Screening` suggests likely IPC classes for a patent idea based on its extracted technical features
- stored patent records can display human-readable IPC labels when they have IPC codes

### Technical feature families

The NLP layer groups extracted features into a few engineering-friendly families:

- `Structure`: physical components, zones, interfaces, and stack-up details
- `Material`: glass, polymers, coatings, adhesives, films, and other substance choices
- `Control`: sensors, electrical paths, busbars, controllers, and logic
- `Manufacturing`: bonding, laminating, assembly, forming, coating, and process steps
- `Performance`: thermal, optical, acoustic, durability, and other target effects

This keeps filtering and comparison simple while still useful for engineering review.

## Current demo scope

- Text-based patent ingestion via the UI
- AI-assisted patent feature extraction for claims and descriptions when enabled
- Synthetic automotive glazing patents for development and evaluation
- Product design comparison with transparent scoring logic
- Structured design-around suggestions from detected overlaps
- Early multi-patent innovation summary

## Next recommended steps

1. Validate AI-assisted extraction quality on a few real partner-approved patent texts.
2. Add manual accept/edit workflows for extracted features in the review UI.
3. Add one real live data adapter, for example a watched folder of partner-approved patent exports.
4. Replace SQLite with PostgreSQL when multi-user deployment becomes necessary.

Architecture details are documented in [docs/architecture.md](docs/architecture.md).
