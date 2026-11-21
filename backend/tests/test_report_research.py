"""Tests for ``run/report --research``: reuse, failure handling and output."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from tests.test_research import ScriptedCLI, settings
from tests.test_research import db_path as _db_path  # noqa: F401 - fixture

from src.config import LLMSettings
from src.database import db
from src.llm import LLMClient
from src.main import main
from src.reporting.pdf import generate_report
from src.reporting.summary import build_text_summary
from src.research.digest import research_for_report, stored_digests
from src.research.prompts import PROMPT_VERSION

db_path = _db_path


def _crystal_id(path) -> int:
    rows = db.list_ipos(limit=10, db_path=path)
    return next(int(r["id"]) for r in rows if r["name"].startswith("Crystal"))


def _research(path, cli, **kwargs):
    ipo_id = _crystal_id(path)
    client = LLMClient(settings(), runner=cli)
    digests = research_for_report(
        [ipo_id], client=client, db_path=path, **{"max_age_hours": 24, **kwargs}
    )
    return ipo_id, digests[ipo_id]


def _model_calls(cli) -> int:
    return sum(1 for call in cli.calls if "--model" in call["command"])


def test_runs_research_when_missing(db_path):
    cli = ScriptedCLI()
    _, digest = _research(db_path, cli)

    assert digest.status == "new"
    assert digest.verdict == "Watch"
    assert digest.confidence == "medium"
    assert digest.strengths[0] == "growth"
    assert digest.disputes == 1
    assert digest.note is None
    assert _model_calls(cli) > 0


def test_reuses_fresh_research_and_reruns_when_old(db_path):
    _research(db_path, ScriptedCLI())

    cli = ScriptedCLI()
    _, reused = _research(db_path, cli)
    assert reused.status == "reused"
    assert _model_calls(cli) == 0

    later = datetime.now(UTC) + timedelta(hours=30)
    _, rerun = _research(db_path, cli, now=later)
    assert rerun.status == "new"
    assert _model_calls(cli) > 0


def test_failure_keeps_previous_result_with_note(db_path):
    _, first = _research(db_path, ScriptedCLI())

    _, digest = _research(db_path, ScriptedCLI(fail_on="synthesis"), max_age_hours=0)

    assert digest.status == "failed"
    assert digest.verdict == "Watch"  # previous completed run
    assert digest.run_id == first.run_id
    assert "failed" in digest.note and "previous result" in digest.note


def test_ai_disabled_is_reported_not_raised(db_path):
    ipo_id = _crystal_id(db_path)
    client = LLMClient(LLMSettings(enabled=False), runner=ScriptedCLI())

    digest = research_for_report(
        [ipo_id], client=client, max_age_hours=24, db_path=db_path
    )[ipo_id]

    assert digest.status == "unavailable"
    assert not digest.has_result
    assert "unavailable" in digest.note


def test_in_progress_run_is_not_duplicated(db_path):
    ipo_id = _crystal_id(db_path)
    db.create_research_run(ipo_id, prompt_version=PROMPT_VERSION, db_path=db_path)
    cli = ScriptedCLI()

    _, digest = _research(db_path, cli)

    assert digest.status == "in_progress"
    assert _model_calls(cli) == 0


def test_stored_digests_never_run_anything(db_path):
    ipo_id = _crystal_id(db_path)
    assert stored_digests([ipo_id], db_path=db_path)[ipo_id].status == "none"


@pytest.fixture
def researched(db_path):
    ipo_id, digest = _research(db_path, ScriptedCLI())
    return db_path, ipo_id, digest


def test_text_summary_and_pdf_include_research(researched, tmp_path):
    from tests.test_reporting import make_analysis

    _, ipo_id, digest = researched
    analysis = make_analysis().model_copy(update={"ipo_id": ipo_id})

    text = build_text_summary(
        [analysis], min_gmp_percent=20, research={ipo_id: digest}
    )
    assert "AI research: Watch (medium confidence, 1 dispute)" in text
    assert "AI strength: growth" in text
    assert "AI risk: concentration" in text

    plain = build_text_summary([analysis], min_gmp_percent=20)
    assert "AI research" not in plain

    path = generate_report(
        [analysis],
        output_path=tmp_path / "ai.pdf",
        min_gmp_percent=20,
        research={ipo_id: digest},
    )
    assert path.read_bytes().startswith(b"%PDF")


def test_cli_report_research_end_to_end(db_path, tmp_path, monkeypatch, capsys):
    cli = ScriptedCLI()
    monkeypatch.setattr(
        "src.llm.LLMClient", lambda _settings: LLMClient(settings(), runner=cli)
    )
    output = tmp_path / "scheduled.pdf"

    code = main(
        [
            "--db-path",
            str(db_path),
            "report",
            "--min-gmp",
            "0",
            "--research",
            "--output",
            str(output),
        ]
    )

    assert code == 0
    assert output.read_bytes().startswith(b"%PDF")
    printed = capsys.readouterr().out
    assert "AI research: Watch" in printed
    assert _model_calls(cli) > 0


def test_cli_report_research_survives_ai_off(db_path, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        "src.llm.LLMClient",
        lambda _settings: LLMClient(LLMSettings(enabled=False)),
    )
    output = tmp_path / "off.pdf"

    code = main(
        [
            "--db-path",
            str(db_path),
            "report",
            "--min-gmp",
            "0",
            "--research",
            "--output",
            str(output),
        ]
    )

    assert code == 0
    assert output.exists()
    assert "AI research unavailable" in capsys.readouterr().out
