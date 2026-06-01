# Architecture Notes

## 1. Prototype boundary

The first implementation slice intentionally covers the must-have flow from the requirements:

1. Ingest a patent as text.
2. Split it into sections.
3. Extract normalized technical features with source evidence.
4. Store the structured result in a database.
5. Accept a product design description.
6. Extract design features in the same format.
7. Compare product features against patent features.
8. Produce an explainable risk score and design-around suggestions.

That keeps the first usable version aligned with Phase 1 and Phase 2 while leaving extension points for Phase 3 and Phase 4.
The current revision now uses AI-assisted extraction for patent claims and descriptions when enabled, with a deterministic fallback path when the model is unavailable or returns unusable output.

## 2. Chosen libraries

### Backend

- `FastAPI`
  - Good fit for Python-first development.
  - Easy to host locally with `uvicorn`.
  - Clean future path for APIs, authentication, and private deployment.

### Frontend

- `Jinja2` server-rendered templates
  - Fast to prototype.
  - No separate frontend build pipeline needed.
  - Easy to host inside a private environment for the industry partner.
  - Good stepping stone if a richer React frontend is needed later.

### Storage

- `sqlite3` from the Python standard library
  - Zero extra dependency for the prototype.
  - Enough for a local single-user or small-team workflow.
  - Repository layer is isolated so it can later be replaced with PostgreSQL.

### AI integration

- Hybrid extraction strategy
  - OpenRouter can perform structured patent feature extraction and richer design-around generation.
  - The rule-based extractor remains in place as a deterministic fallback and baseline.
  - This keeps the prototype usable even when the model is unavailable or a response is malformed.

## 3. Module layout

### Core application

- `src/patent_analysis/app.py`
  - FastAPI application, routes, dependency wiring.

- `src/patent_analysis/cli.py`
  - Command entrypoints for running the server and maintenance tasks.

- `src/patent_analysis/runtime.py`
  - Shared runtime assembly for settings, repository access, extractor wiring, and demo bootstrap.

- `src/patent_analysis/config.py`
  - Loads `settings.local.toml` or falls back to `settings.example.toml`.

- `src/patent_analysis/database.py`
  - SQLite schema creation and connection helpers.

- `src/patent_analysis/repository.py`
  - Central persistence layer for patents, features, product designs, assessments, and suggestions.

### Services

- `services/normalization.py`
  - Shared token cleanup and canonical term normalization.

- `services/extraction.py`
  - Hybrid feature extraction service.
  - Uses OpenRouter structured JSON extraction for patent claims and descriptions when enabled.
  - Falls back to heuristic extraction when needed.
  - Assigns each extracted feature to a compact engineering taxonomy for filtering and screening.

- `services/risk.py`
  - Patent-to-product comparison and explainable scoring.

- `services/screening.py`
  - Patent-to-patent and idea-to-library screening using the same extracted features.
  - Adds simple engineering review signals such as crowded features, distinctive features, and missing detail prompts.

- `services/ipc_scheme.py`
  - Parses DPMA IPC scheme XML files.
  - Converts between compact scheme symbols and engineer-facing IPC codes.
  - Suggests likely IPC classes for a patent idea or patent text.

- `services/taxonomy.py`
  - Defines the technical feature families used across extraction, filtering, and screening.

- `services/suggestions.py`
  - Rule-based design-around suggestions, with optional OpenRouter augmentation.

- `services/innovation.py`
  - Early multi-patent theme and whitespace summary.

- `services/llm.py`
  - Optional OpenRouter client with live connectivity checks and structured JSON support.

### Data source adapters

- `sources/demo.py`
  - Loads the synthetic demo patents and designs.

- `sources/directory.py`
  - Reads future local patent import files from a folder.

- `sources/dpma_xml.py`
  - Parses downloaded DPMA-style XML full text files into the shared patent document model.

This adapter pattern is the main extension point for future live sources.

## 4. Why this frontend choice

For this stage, a server-rendered web app is the best tradeoff:

- easy to test on `localhost`,
- easy to demo to supervisors,
- easier to package in Docker or deploy behind a private reverse proxy,
- keeps the whole project Python-centric while the data and analysis pipeline is still evolving.

If the partner later needs heavier workflow interaction, we can keep the FastAPI backend and replace only the UI layer.

## 5. How to add live patent databases later

The current code is prepared for three source classes:

1. `demo_json`
   - synthetic data for development and evaluation

2. `directory`
   - approved `.json`, `.txt`, or `.md` files dropped into `data/live_patents/`

3. future remote connectors
   - partner export API
   - internal document management system
   - database dump or scheduled ETL feed

To add a new live source cleanly:

1. Create a new adapter implementing the same source interface.
2. Normalize the incoming patent structure into the shared patent document model.
3. Register the adapter in the source registry.
4. Add source-specific config values in `settings.local.toml`.

That way, ingestion changes do not affect extraction, scoring, or the UI.

For the current real-patent workflow, the system favors offline import of downloaded DPMA XML packages rather than a live network dependency. This keeps the prototype simple, reproducible, and deployable on a local machine without background jobs.

The IPC scheme is imported separately from the patent library because DPMA's `DE_ExportIPC.xml` is a classification reference file rather than a corpus of patent full texts. In the app, it acts as a searchable classification layer and as a lightweight IPC recommendation aid during screening.

## 6. Data model direction

The SQLite schema mirrors the requirements:

- `patents`
- `patent_sections`
- `extracted_features`
- `product_designs`
- `product_features`
- `risk_assessments`
- `feature_matches`
- `design_suggestions`
- `innovation_insights`

Feature rows now also record extraction metadata so reviewers can see whether a feature came from the AI-assisted path or the rule-based fallback.

This is intentionally close to the requirement document so we keep traceability between the written specification and the implementation.

## 7. Deployment path

### Local prototype now

- `./.venv/bin/python main.py`
- SQLite file in `data/`
- localhost access only

### Private industry deployment later

- same FastAPI app
- environment-specific config file
- Docker container or virtual machine deployment
- reverse proxy such as Nginx
- swap SQLite to PostgreSQL
- add authentication and access control

## 8. Intentional limitations of this first version

- no CAD-native integration yet
- no legal advice or legal automation
- no heavy embedding stack yet
- no multi-user auth yet
- live remote patent connectors are designed but not activated

That keeps the system aligned with the current scope and avoids premature complexity.
