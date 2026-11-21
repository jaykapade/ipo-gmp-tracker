"""Offline tests for the AI research pipeline, its storage and API.

The ``claude`` CLI is replaced by :class:`ScriptedCLI`, which answers each
call according to the JSON schema it was given (or the web tools it was
allowed), and records every prompt so isolation rules can be asserted.
"""

from __future__ import annotations

import json
import subprocess

import pytest
from fastapi.testclient import TestClient

from src.api.main import create_app
from src.config import LLMSettings, RoleOverride
from src.database import db
from src.database.migrations import apply_migrations
from src.llm import LLMClient
from src.models.ipo import IPO
from src.research import ResearchError, ResearchJobs, run_research
from src.research.orchestrator import apply_citation_gate
from src.research.schemas import EvidencePoint, Perspective
from src.utils.normalization import normalize_name

# --- Fake CLI ----------------------------------------------------------------

GATHER = {
    "facts": [
        {
            "category": "financials",
            "claim": "Revenue from operations",
            "value": "₹2,100 cr",
            "period": "FY25",
            "source_url": "https://example.com/rhp.pdf",
            "source_title": "RHP",
            "source_type": "official",
        },
        {
            "category": "risk",
            "claim": "Top five customers share of revenue",
            "value": "48%",
            "period": "FY25",
            "source_url": "https://example.com/rhp.pdf",
            "source_type": "official",
        },
        {  # duplicate of the first fact: must be de-duplicated
            "category": "financials",
            "claim": "Revenue from operations",
            "value": "₹2,100 cr",
            "source_url": "https://news.example.com/a",
            "source_type": "secondary",
        },
    ],
    "gaps": ["peer multiples"],
    "rhp_url": "https://example.com/rhp.pdf",
}


def perspective(points):
    return {
        "evidence": [{"point": p, "fact_ids": ids} for p, ids in points],
        "conclusion": "Mixed picture.",
        "confidence": {"level": "medium", "reason": "partial disclosure"},
        "missing_information": ["peer multiples"],
    }


class ScriptedCLI:
    """Answers ``claude -p`` calls by inspecting the requested schema."""

    def __init__(self, *, fail_on: str | None = None, disagree: bool = True):
        self.calls: list[dict] = []
        self.fail_on = fail_on
        self.disagree = disagree

    @staticmethod
    def _flag(command, name):
        return command[command.index(name) + 1] if name in command else None

    def __call__(self, command, **kwargs):
        self.calls.append({"command": command, **kwargs})
        if command[1:] == ["auth", "status"]:
            return self._ok({"loggedIn": True, "authMethod": "claude.ai"}, raw=True)

        schema = json.loads(self._flag(command, "--json-schema") or "{}")
        props = set(schema.get("properties", {}))
        kind = (
            "gather"
            if "facts" in props
            else "perspective"
            if "evidence" in props
            else "verify"
            if "reviews" in props
            else "challenge"
            if "rulings" in props
            else "synthesis"
            if "verdict" in props
            else "plain"
        )
        if kind == self.fail_on:
            return subprocess.CompletedProcess(command, 1, "", "boom")

        prompt = kwargs.get("input") or ""
        if kind == "gather":
            body = GATHER
        elif kind == "perspective":
            body = perspective(
                [
                    ("Revenue reached ₹2,100 cr.", ["W1"]),
                    ("Customer concentration is high.", ["W2", "D1"]),
                    ("Invented claim.", ["Z9"]),  # unknown id: gate drops it
                ]
            )
        elif kind == "verify":
            body = {
                "reviews": [
                    {"finding_id": "h1.1", "stance": "agree", "reason": "ok"},
                    {
                        "finding_id": "h2.2",
                        "stance": "disagree" if self.disagree else "agree",
                        "reason": "48% is moderate for the sector",
                    },
                ]
            }
        elif kind == "challenge":
            body = {
                "rulings": [
                    {
                        "finding_id": "h2.2",
                        "ruling": "uphold_verifier",
                        "reason": "evidence is ambiguous",
                    }
                ]
            }
        elif kind == "synthesis":
            body = {
                "verdict": "Watch",
                "conclusion": "Decent growth, concentration risk.",
                "strengths": ["growth", "scale", "listing demand"],
                "risks": ["concentration", "valuation", "secondary data"],
                "what_would_change": ["peer multiples"],
                "confidence": {"level": "medium", "reason": "partial"},
            }
        else:
            body = {"text": prompt}
        return self._ok(body)

    @staticmethod
    def _ok(body, *, raw=False):
        if raw:
            return subprocess.CompletedProcess([], 0, json.dumps(body), "")
        payload = {
            "type": "result",
            "is_error": False,
            "result": json.dumps(body),
            "structured_output": body,
            "usage": {"input_tokens": 100, "output_tokens": 50},
        }
        return subprocess.CompletedProcess([], 0, json.dumps(payload), "")

    def prompts(self, model: str) -> list[str]:
        return [
            c.get("input") or ""
            for c in self.calls
            if self._flag(c["command"], "--model") == model
        ]


def settings(*, challenger: bool = True) -> LLMSettings:
    roles = {
        "analyst": RoleOverride(model="claude-sonnet-5-5"),
        "verifier": RoleOverride(model="claude-opus-5-5"),
        "extractor": RoleOverride(model="claude-haiku-5-5"),
    }
    if challenger:
        roles["challenger"] = RoleOverride(model="claude-opus-4-challenger")
    return LLMSettings(
        enabled=True,
        provider="claude-code",
        model="claude-sonnet-5-5",
        allow_cloud=True,
        roles=roles,
    )


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "research.db"
    db.save_ipo_with_gmp(
        IPO(
            name="Crystal Crop Protection",
            normalized_name=normalize_name("Crystal Crop Protection"),
            category="IPO",
            status="open",
            issue_price=272.0,
            issue_price_lower=259.0,
            issue_price_upper=272.0,
            ipo_size_cr="455.49",
            subscription=16.3,
            pe=28.2,
            close_date="2099-01-01",
            gmp=40.0,
            gmp_percent=14.7,
        ),
        "test",
        db_path=path,
    )
    db.save_ipo_with_gmp(
        IPO(
            name="Tiny SME",
            normalized_name=normalize_name("Tiny SME"),
            category="SME",
            status="open",
            issue_price=50.0,
            gmp=5.0,
            gmp_percent=10.0,
        ),
        "test",
        db_path=path,
    )
    return path


# --- Unit --------------------------------------------------------------------


def test_citation_gate_drops_unknown_ids():
    raw = Perspective(
        evidence=[
            EvidencePoint(point="a", fact_ids=["W1", "X1"]),
            EvidencePoint(point="b", fact_ids=["X2"]),
            EvidencePoint(point="c", fact_ids=[]),
        ],
        conclusion="c",
        confidence={"level": "low", "reason": "r"},
    )
    gated, dropped = apply_citation_gate(raw, {"W1"})

    assert [(e.point, e.fact_ids) for e in gated.evidence] == [("a", ["W1"])]
    assert dropped == ["b", "c"]


# --- Pipeline ----------------------------------------------------------------


def test_full_pipeline_persists_every_stage(db_path):
    cli = ScriptedCLI()
    client = LLMClient(settings(), runner=cli)
    stages: list[str] = []

    result = run_research(1, client=client, db_path=db_path, on_stage=stages.append)

    assert stages == [
        "gather",
        "perspectives",
        "verify",
        "challenge",
        "synthesis",
        "done",
    ]
    # Web facts are de-duplicated and DB facts are merged in.
    ids = [f.id for f in result.fact_pack.facts]
    assert ids[:2] == ["W1", "W2"] and "W3" not in ids
    assert any(i.startswith("D") for i in ids)
    assert result.fact_pack.rhp_url == "https://example.com/rhp.pdf"

    # Citation gate removed the invented claim from each perspective.
    assert len(result.perspectives) == 4
    for record in result.perspectives:
        assert [e.point for e in record.evidence] == [
            "Revenue reached ₹2,100 cr.",
            "Customer concentration is high.",
        ]
        assert record.dropped_evidence == ["Invented claim."]

    # Verifier disagreement became a dispute; the challenger ruled on it.
    assert [d.finding_id for d in result.disputes] == ["h2.2"]
    assert result.disputes[0].ruling == "uphold_verifier"
    assert result.challenger_used is True
    assert result.assessment.verdict == "Watch"

    run = db.get_latest_research(1, db_path=db_path)
    assert run["status"] == "done" and run["stage"] == "done"
    kinds = [o["kind"] for o in run["outputs"]]
    assert kinds == [
        "facts",
        "h1",
        "h2",
        "h3",
        "h4",
        "verification",
        "challenge",
        "disputes",
        "h5",
    ]
    h5 = run["outputs"][-1]
    assert h5["provider"] == "claude-code"
    assert h5["model"] == "claude-sonnet-5-5"
    assert h5["data_left_machine"] is True
    assert h5["input_tokens"] == 100
    assert h5["input_hash"]


def test_roles_route_to_their_models_and_gather_uses_web_tools(db_path):
    cli = ScriptedCLI()
    run_research(1, client=LLMClient(settings(), runner=cli), db_path=db_path)

    gather_call = cli.calls[0]["command"]
    assert ScriptedCLI._flag(gather_call, "--tools") == "WebSearch,WebFetch"
    assert ScriptedCLI._flag(gather_call, "--model") == "claude-haiku-5-5"
    assert "Crystal Crop Protection" in cli.calls[0]["input"]
    assert "₹259–₹272" in cli.calls[0]["input"]

    others = [c["command"] for c in cli.calls[1:]]
    assert all(ScriptedCLI._flag(c, "--tools") == "" for c in others)
    assert len(cli.prompts("claude-sonnet-5-5")) == 5  # H1–H4 + H5
    assert len(cli.prompts("claude-opus-5-5")) == 1  # verifier
    assert len(cli.prompts("claude-opus-4-challenger")) == 1


def test_perspectives_are_isolated_and_verifier_sees_no_reasoning(db_path):
    cli = ScriptedCLI()
    run_research(1, client=LLMClient(settings(), runner=cli), db_path=db_path)

    perspective_prompts = cli.prompts("claude-sonnet-5-5")[:4]
    for prompt in perspective_prompts:
        # No perspective sees another perspective's output.
        assert "Customer concentration is high." not in prompt
        assert "Mixed picture." not in prompt
    titles = {p.split("Perspective ")[1].split(".")[0] for p in perspective_prompts}
    assert titles == {
        "H1 — Business quality",
        "H2 — Financial health",
        "H3 — Valuation and pricing",
        "H4 — Risks and red flags",
    }

    verifier_prompt = cli.prompts("claude-opus-5-5")[0]
    assert "[h2.2] Customer concentration is high." in verifier_prompt
    assert "partial disclosure" not in verifier_prompt  # analyst's reasoning


def test_challenger_skipped_when_not_configured(db_path):
    cli = ScriptedCLI()
    result = run_research(
        1, client=LLMClient(settings(challenger=False), runner=cli), db_path=db_path
    )

    assert result.challenger_used is False
    assert result.disputes[0].ruling == "unresolved"
    assert "challenger not configured" in " ".join(result.notes)
    kinds = [o["kind"] for o in db.get_latest_research(1, db_path=db_path)["outputs"]]
    assert "challenge" not in kinds


def test_gather_failure_marks_run_failed(db_path):
    cli = ScriptedCLI(fail_on="gather")
    with pytest.raises(ResearchError):
        run_research(1, client=LLMClient(settings(), runner=cli), db_path=db_path)

    run = db.get_latest_research(1, db_path=db_path)
    assert run["status"] == "failed"
    assert run["stage"] == "gather"
    assert "boom" in run["error"]


def test_research_refuses_when_ai_disabled(db_path):
    with pytest.raises(ResearchError, match="disabled"):
        run_research(1, client=LLMClient(LLMSettings()), db_path=db_path)


# --- Storage -----------------------------------------------------------------


def test_migration_7_is_idempotent(tmp_path):
    import sqlite3

    connection = sqlite3.connect(tmp_path / "m.db")
    apply_migrations(connection)
    assert apply_migrations(connection) == []
    tables = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    assert {"research_runs", "ai_outputs"} <= tables


def test_stale_runs_are_failed_on_startup(db_path):
    run_id = db.create_research_run(1, prompt_version="v", db_path=db_path)
    db.update_research_run(run_id, status="running", stage="verify", db_path=db_path)

    assert db.mark_stale_research_runs_failed(db_path=db_path) == 1
    run = db.get_research_run(run_id, db_path=db_path)
    assert run["status"] == "failed"
    assert "restarted" in run["error"]


def test_jobs_deduplicate_active_runs(db_path):
    jobs = ResearchJobs(LLMClient(settings(), runner=ScriptedCLI()), db_path=db_path)
    jobs._executor.shutdown(wait=True)  # keep runs queued for this test
    jobs._executor = type("Noop", (), {"submit": lambda *a, **k: None})()

    first, created = jobs.submit(1)
    again, created_again = jobs.submit(1)

    assert created is True and created_again is False
    assert first["id"] == again["id"]
    assert first["status"] == "queued"


# --- API ---------------------------------------------------------------------


@pytest.fixture
def api(db_path):
    app = create_app(db_path=db_path, api_token="test-token", llm_settings=settings())
    cli = ScriptedCLI()
    app.state.llm = LLMClient(settings(), runner=cli)
    app.state.research = ResearchJobs(app.state.llm, db_path=db_path)
    with TestClient(app) as client:
        yield client, app


def test_research_endpoints_end_to_end(api):
    client, app = api

    assert client.get("/api/ipos/1/research").json() is None
    assert client.post("/api/ipos/1/research").status_code == 401

    response = client.post(
        "/api/ipos/1/research", headers={"X-API-Token": "test-token"}
    )
    assert response.status_code == 202
    run_id = response.json()["id"]
    assert response.json()["stages"][0] == "gather"

    app.state.research._executor.shutdown(wait=True)

    status = client.get(f"/api/research/runs/{run_id}").json()
    assert status["status"] == "done"

    detail = client.get("/api/ipos/1/research").json()
    assert detail["status"] == "done"
    assert [o["kind"] for o in detail["outputs"]][-1] == "h5"
    assert detail["outputs"][-1]["output"]["verdict"] == "Watch"

    ipo = client.get("/api/ipos/1").json()
    assert ipo["research_status"] == "done"
    assert ipo["research_verdict"] == "Watch"

    listed = client.get("/api/ipos", params={"has_research": True}).json()
    assert [item["name"] for item in listed["items"]] == ["Crystal Crop Protection"]
    assert listed["items"][0]["research_verdict"] == "Watch"


def test_research_endpoints_validate_inputs(api):
    client, _app = api
    headers = {"X-API-Token": "test-token"}
    assert client.post("/api/ipos/999/research", headers=headers).status_code == 404
    assert client.get("/api/ipos/999/research").status_code == 404
    assert client.get("/api/research/runs/999").status_code == 404


def test_research_post_conflicts_when_ai_disabled(db_path):
    app = create_app(db_path=db_path, api_token="t", llm_settings=LLMSettings())
    with TestClient(app) as client:
        response = client.post("/api/ipos/1/research", headers={"X-API-Token": "t"})
    assert response.status_code == 409


def test_facets_and_category_filter(api):
    client, _app = api

    facets = client.get("/api/ipos/facets").json()
    assert facets["total"] == 2
    assert {c["value"]: c["count"] for c in facets["categories"]} == {
        "mainboard": 1,
        "sme": 1,
    }
    assert facets["statuses"] == [{"value": "open", "count": 2}]
    assert facets["screen_floor"] == 20.0
    assert facets["researched"] == 0

    sme = client.get("/api/ipos", params={"category": "sme"}).json()
    assert [i["name"] for i in sme["items"]] == ["Tiny SME"]
    main = client.get("/api/ipos", params={"category": "mainboard"}).json()
    assert [i["name"] for i in main["items"]] == ["Crystal Crop Protection"]
    assert client.get("/api/ipos", params={"category": "x"}).status_code == 422
