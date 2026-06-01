from __future__ import annotations

import json
import time
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import Settings, load_settings
from .repository import PatentRepository
from .runtime import build_runtime
from .services.agent_conflict import ConflictAnalysisAgent
from .services.agent_design import DesignImprovementAgent
from .services.agent_extraction import PatentExtractionAgent
from .services.agent_innovation import InnovationOpportunityAgent
from .services.llm import OpenRouterClient


PACKAGE_DIR  = Path(__file__).resolve().parent
TEMPLATES_DIR = PACKAGE_DIR / "templates"
STATIC_DIR    = PACKAGE_DIR / "static"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    runtime  = build_runtime(settings)
    repo     = runtime.repository
    llm      = runtime.llm_client

    agents = {
        "extraction": PatentExtractionAgent(llm),
        "conflict":   ConflictAnalysisAgent(llm),
        "design":     DesignImprovementAgent(llm),
        "innovation": InnovationOpportunityAgent(llm),
    }

    app = FastAPI(title=settings.app.name)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

    def render(request: Request, name: str, ctx: dict) -> HTMLResponse:
        ctx.setdefault("app_name", settings.app.name)
        ctx.setdefault("request", request)
        return templates.TemplateResponse(request=request, name=name, context=ctx)

    def enrich_patents(patents: list[dict]) -> list[dict]:
        for p in patents:
            cached = repo.get_agent_result(int(p["id"]), "extraction")
            if cached and "result" in cached:
                meta    = cached["result"].get("meta", {}) or {}
                details = cached["result"].get("details", {}) or {}
                risk_text = details.get("risk_analysis") or ""
                risk_level = next(
                    (lvl for lvl in ("Critical", "High", "Medium", "Low")
                     if lvl.lower() in risk_text.lower()), ""
                )
                features = [f for f in (details.get("key_technical_features") or []) if f]
                p["ex_patentee"]  = meta.get("patentee") or ""
                p["ex_date"]      = meta.get("application_date") or ""
                p["ex_status"]    = meta.get("legal_status") or ""
                p["ex_risk"]      = risk_level
                p["ex_features"]  = features[:5]
                p["ex_feat_text"] = " ".join(features).lower()
            else:
                p["ex_patentee"]  = ""
                p["ex_date"]      = ""
                p["ex_status"]    = ""
                p["ex_risk"]      = ""
                p["ex_features"]  = []
                p["ex_feat_text"] = ""
        return patents

    # ── Redirect root → analyze ───────────────────────────────

    @app.get("/", response_class=HTMLResponse)
    async def root():
        return RedirectResponse(url="/analyze")

    # ── Analysis dashboard ────────────────────────────────────

    @app.get("/analyze", response_class=HTMLResponse)
    async def analyze_home(request: Request):
        return render(request, "analyze.html", {
            "title": "Analysis Dashboard",
            "patents": enrich_patents(repo.list_patents(limit=200)),
            "patent_id": None,
            "selected": None,
            "has_pdf": False,
            "agent_results_json": "{}",
            "nav": "analyze",
        })

    @app.get("/analyze/{patent_id}", response_class=HTMLResponse)
    async def analyze_patent(request: Request, patent_id: int):
        patent = repo.get_patent(patent_id)
        if patent is None:
            raise HTTPException(status_code=404, detail="Patent not found.")
        agent_results = {
            agent: repo.get_agent_result(patent_id, agent)
            for agent in ("extraction", "conflict", "design", "innovation")
        }
        return render(request, "analyze.html", {
            "title": f"Analyse — {patent['title']}",
            "patents": enrich_patents(repo.list_patents(limit=200)),
            "patent_id": patent_id,
            "selected": patent,
            "has_pdf": bool(patent.get("pdf_path")),
            "agent_results_json": json.dumps(agent_results),
            "nav": "analyze",
        })

    # ── PDF upload ────────────────────────────────────────────

    @app.post("/api/patents/upload-pdf")
    async def upload_pdf(file: UploadFile = File(...)):
        if not file.filename or not file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

        pdf_bytes = await file.read()
        if not pdf_bytes:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        upload_dir = settings.root_dir / "data" / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
        safe_name = f"{int(time.time())}_{file.filename.replace(' ', '_')}"
        pdf_path  = upload_dir / safe_name
        pdf_path.write_bytes(pdf_bytes)

        title      = file.filename.removesuffix(".pdf").replace("_", " ").replace("-", " ")
        patent_id  = repo.create_patent(title, source="pdf-upload")
        repo.update_patent(patent_id, pdf_path=str(pdf_path))

        result = agents["extraction"].run(pdf_bytes)
        repo.save_agent_result(patent_id, "extraction", result)

        if "meta" in result and result["meta"]:
            updates: dict[str, str] = {}
            if result["meta"].get("patent_number"):
                updates["patent_number"] = str(result["meta"]["patent_number"])
            if result["meta"].get("patentee"):
                updates["title"] = str(result["meta"]["patentee"])
            if updates:
                repo.update_patent(patent_id, **updates)

        return JSONResponse({"patent_id": patent_id, "result": result})

    # ── Agent endpoints ───────────────────────────────────────

    @app.post("/api/patents/{patent_id}/agents/extraction")
    async def run_extract(patent_id: int):
        patent = repo.get_patent(patent_id)
        if not patent or not patent.get("pdf_path"):
            raise HTTPException(status_code=404, detail="No PDF found for this patent.")
        pdf_bytes = Path(patent["pdf_path"]).read_bytes()
        result = agents["extraction"].run(pdf_bytes)
        repo.save_agent_result(patent_id, "extraction", result)
        return JSONResponse(result)

    @app.get("/api/patents/{patent_id}/agents/extraction")
    async def get_extract(patent_id: int):
        cached = repo.get_agent_result(patent_id, "extraction")
        if cached is None:
            raise HTTPException(status_code=404, detail="No extraction result yet.")
        return JSONResponse(cached)

    @app.post("/api/patents/{patent_id}/agents/conflict")
    async def run_conflict(patent_id: int):
        extraction = repo.get_agent_result(patent_id, "extraction")
        if extraction is None:
            raise HTTPException(status_code=400, detail="Run Agent 1 (extraction) first.")
        db_patents = repo.list_patents_with_agent_results(exclude_id=patent_id)
        result = agents["conflict"].run(extraction["result"], db_patents)
        repo.save_agent_result(patent_id, "conflict", result)
        return JSONResponse(result)

    @app.get("/api/patents/{patent_id}/agents/conflict")
    async def get_conflict(patent_id: int):
        cached = repo.get_agent_result(patent_id, "conflict")
        if cached is None:
            raise HTTPException(status_code=404, detail="No conflict result yet.")
        return JSONResponse(cached)

    @app.post("/api/patents/{patent_id}/agents/design")
    async def run_design(patent_id: int):
        extraction = repo.get_agent_result(patent_id, "extraction")
        conflict   = repo.get_agent_result(patent_id, "conflict")
        if extraction is None:
            raise HTTPException(status_code=400, detail="Run Agent 1 (extraction) first.")
        if conflict is None:
            raise HTTPException(status_code=400, detail="Run Agent 2 (conflict) first.")
        db_patents = repo.list_patents_with_agent_results(exclude_id=patent_id)
        result = agents["design"].run(extraction["result"], db_patents, conflict["result"])
        repo.save_agent_result(patent_id, "design", result)
        return JSONResponse(result)

    @app.get("/api/patents/{patent_id}/agents/design")
    async def get_design(patent_id: int):
        cached = repo.get_agent_result(patent_id, "design")
        if cached is None:
            raise HTTPException(status_code=404, detail="No design result yet.")
        return JSONResponse(cached)

    @app.post("/api/patents/{patent_id}/agents/innovation")
    async def run_innovation(patent_id: int):
        extraction = repo.get_agent_result(patent_id, "extraction")
        if extraction is None:
            raise HTTPException(status_code=400, detail="Run Agent 1 (extraction) first.")
        db_patents = repo.list_patents_with_agent_results(exclude_id=patent_id)
        result = agents["innovation"].run(extraction["result"], db_patents)
        repo.save_agent_result(patent_id, "innovation", result)
        return JSONResponse(result)

    @app.get("/api/patents/{patent_id}/agents/innovation")
    async def get_innovation(patent_id: int):
        cached = repo.get_agent_result(patent_id, "innovation")
        if cached is None:
            raise HTTPException(status_code=404, detail="No innovation result yet.")
        return JSONResponse(cached)

    # ── Delete patent ─────────────────────────────────────────

    @app.delete("/api/patents/{patent_id}")
    async def delete_patent(patent_id: int):
        pdf_path = repo.delete_patent(patent_id)
        if pdf_path:
            try:
                Path(pdf_path).unlink(missing_ok=True)
            except OSError:
                pass
        return JSONResponse({"ok": True})

    return app
