"""Research orchestration (framework section H0).

    gather      researcher role: web facts + DB facts -> fact pack
    perspectives H1–H4, analyst role, each in a fresh isolated context
    citation gate drop evidence that cites unknown fact ids
    verify      verifier role challenges every finding -> dispute log
    challenge   challenger role rules on disputes (only if configured)
    synthesis   H5, analyst role: perspectives + disputes + deterministic score

Every model output is stored in ``ai_outputs`` with provider, model, prompt
version, input hash and token usage. The deterministic score is never
modified; H5 is shown beside it.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.database import db
from src.llm.base import LLMError, LLMMessage
from src.llm.providers import is_cloud_provider
from src.research.gather import gather_facts, render_facts
from src.research.prompts import (
    CHALLENGER_SYSTEM,
    PERSPECTIVE_SYSTEM,
    PERSPECTIVES,
    PROMPT_VERSION,
    SYNTHESIS_SYSTEM,
    VERIFIER_SYSTEM,
    PerspectiveSpec,
)
from src.research.schemas import (
    Assessment,
    ChallengerReview,
    Confidence,
    Dispute,
    FactPack,
    Perspective,
    PerspectiveRecord,
    VerifierReview,
)

if TYPE_CHECKING:
    from src.llm import LLMClient, LLMResponse

logger = logging.getLogger(__name__)

STAGES: tuple[str, ...] = (
    "gather",
    "perspectives",
    "verify",
    "challenge",
    "synthesis",
    "done",
)

StageCallback = Callable[[str], None]


class ResearchError(Exception):
    """A research run could not complete."""


@dataclass
class ResearchResult:
    run_id: int
    fact_pack: FactPack
    perspectives: list[PerspectiveRecord]
    disputes: list[Dispute]
    assessment: Assessment
    challenger_used: bool = False
    notes: list[str] = field(default_factory=list)


# --- Helpers -----------------------------------------------------------------


def _hash_messages(messages: list[LLMMessage]) -> str:
    payload = "\x1e".join(f"{m.role}:{m.content}" for m in messages)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _save(
    *,
    ipo_id: int,
    run_id: int,
    kind: str,
    output: Any,
    response: LLMResponse | None,
    messages: list[LLMMessage] | None,
    db_path: str | Path | None,
    citations: Any = None,
    confidence: str | None = None,
) -> None:
    usage = response.usage if response is not None else None
    db.save_ai_output(
        ipo_id=ipo_id,
        run_id=run_id,
        kind=kind,
        output=output,
        prompt_version=PROMPT_VERSION,
        provider=response.provider if response else None,
        model=response.model if response else None,
        input_hash=_hash_messages(messages) if messages else None,
        citations=citations,
        confidence=confidence,
        input_tokens=usage.input_tokens if usage else None,
        output_tokens=usage.output_tokens if usage else None,
        data_left_machine=bool(response and is_cloud_provider(response.provider)),
        db_path=db_path,
    )


def apply_citation_gate(
    perspective: Perspective, valid_ids: set[str]
) -> tuple[Perspective, list[str]]:
    """Drop evidence whose citations are missing or unknown.

    Unknown ids are removed from a point; a point left with no valid citation
    is dropped entirely and reported.
    """

    kept = []
    dropped: list[str] = []
    for item in perspective.evidence:
        ids = [fact_id for fact_id in item.fact_ids if fact_id in valid_ids]
        if ids:
            kept.append(item.model_copy(update={"fact_ids": ids}))
        else:
            dropped.append(item.point)
    return perspective.model_copy(update={"evidence": kept}), dropped


def _perspective_messages(spec: PerspectiveSpec, facts_text: str, name: str) -> list:
    return [
        LLMMessage("system", PERSPECTIVE_SYSTEM),
        LLMMessage(
            "user",
            f"IPO: {name}\n\nPerspective {spec.key.upper()} — {spec.title}.\n"
            f"Focus: {spec.focus}\n\nEvidence:\n{facts_text}",
        ),
    ]


def _findings_text(perspectives: list[PerspectiveRecord]) -> tuple[str, dict]:
    """Number every finding as ``h<k>.<n>``; returns text and an id index."""

    lines: list[str] = []
    index: dict[str, tuple[str, str]] = {}
    for record in perspectives:
        if record.error:
            continue
        lines.append(f"{record.key.upper()} {record.title}:")
        for number, item in enumerate(record.evidence, start=1):
            finding_id = f"{record.key}.{number}"
            index[finding_id] = (record.key, item.point)
            lines.append(
                f"  [{finding_id}] {item.point} (cites {', '.join(item.fact_ids)})"
            )
        conclusion_id = f"{record.key}.c"
        index[conclusion_id] = (record.key, record.conclusion)
        lines.append(f"  [{conclusion_id}] Conclusion: {record.conclusion}")
    return "\n".join(lines), index


# --- Pipeline ----------------------------------------------------------------


def run_research(
    ipo_id: int,
    *,
    client: LLMClient,
    db_path: str | Path | None = None,
    run_id: int | None = None,
    on_stage: StageCallback | None = None,
) -> ResearchResult:
    """Run the full research pipeline for one IPO and persist every output.

    Creates a run when ``run_id`` is not given. Any failure marks the run
    ``failed`` with the error and raises :class:`ResearchError`.
    """

    ipo = db.get_ipo(ipo_id, db_path=db_path)
    if ipo is None:
        raise ResearchError(f"IPO {ipo_id} not found")
    if run_id is None:
        run_id = db.create_research_run(
            ipo_id, prompt_version=PROMPT_VERSION, db_path=db_path
        )

    def stage(name: str) -> None:
        db.update_research_run(run_id, status="running", stage=name, db_path=db_path)
        if on_stage is not None:
            on_stage(name)

    try:
        result = _run(ipo, run_id=run_id, client=client, db_path=db_path, stage=stage)
    except Exception as exc:
        logger.exception("Research run %s for IPO %s failed", run_id, ipo_id)
        db.update_research_run(
            run_id,
            status="failed",
            error=str(exc) or type(exc).__name__,
            db_path=db_path,
        )
        raise ResearchError(str(exc)) from exc

    db.update_research_run(run_id, status="done", stage="done", db_path=db_path)
    if on_stage is not None:
        on_stage("done")
    return result


def _run(
    ipo: dict[str, Any],
    *,
    run_id: int,
    client: LLMClient,
    db_path: str | Path | None,
    stage: StageCallback,
) -> ResearchResult:
    ipo_id = int(ipo["id"])
    name = str(ipo["name"])
    analyst = client.for_role("analyst")
    if not analyst.enabled:
        raise ResearchError("AI is disabled (set LLM_ENABLED=true)")
    notes: list[str] = []

    # 1. Gather ------------------------------------------------------------
    stage("gather")
    analysis = db.get_latest_analysis(ipo_id, db_path=db_path)
    pack, gather_response = gather_facts(
        ipo,
        gmp_history=db.get_gmp_history(ipo_id, db_path=db_path),
        analysis=analysis,
        researcher=client.for_role("researcher"),
    )
    _save(
        ipo_id=ipo_id,
        run_id=run_id,
        kind="facts",
        output=pack,
        response=gather_response,
        messages=None,
        db_path=db_path,
        citations=sorted({f.source_url for f in pack.facts if f.source_url}),
    )
    facts_text = render_facts(pack)
    valid_ids = pack.ids()

    # 2. Perspectives H1–H4, isolated, in parallel ------------------------
    stage("perspectives")

    def one(spec: PerspectiveSpec) -> tuple[PerspectiveRecord, Any, list]:
        messages = _perspective_messages(spec, facts_text, name)
        try:
            response = analyst.generate(
                messages, response_schema=Perspective, prompt_version=PROMPT_VERSION
            )
        except LLMError as exc:
            record = PerspectiveRecord(
                key=spec.key,
                title=spec.title,
                evidence=[],
                conclusion="Not generated.",
                confidence=Confidence(level="low", reason="generation failed"),
                error=str(exc),
            )
            return record, None, messages
        gated, dropped = apply_citation_gate(response.parsed, valid_ids)
        record = PerspectiveRecord(
            key=spec.key,
            title=spec.title,
            dropped_evidence=dropped,
            **gated.model_dump(),
        )
        return record, response, messages

    with ThreadPoolExecutor(max_workers=len(PERSPECTIVES)) as pool:
        outcomes = list(pool.map(one, PERSPECTIVES))

    perspectives: list[PerspectiveRecord] = []
    for record, response, messages in outcomes:
        perspectives.append(record)
        _save(
            ipo_id=ipo_id,
            run_id=run_id,
            kind=record.key,
            output=record,
            response=response,
            messages=messages,
            db_path=db_path,
            citations=sorted({i for e in record.evidence for i in e.fact_ids}),
            confidence=record.confidence.level,
        )
    failed = [p.key for p in perspectives if p.error]
    if len(failed) == len(perspectives):
        raise ResearchError("every perspective failed: " + perspectives[0].error)
    if failed:
        notes.append(f"perspectives not generated: {', '.join(failed)}")

    # 3. Verify -------------------------------------------------------------
    stage("verify")
    findings_text, finding_index = _findings_text(perspectives)
    verify_messages = [
        LLMMessage("system", VERIFIER_SYSTEM),
        LLMMessage(
            "user",
            f"IPO: {name}\n\nFindings to verify:\n{findings_text}\n\n"
            f"Evidence:\n{facts_text}",
        ),
    ]
    disputes: list[Dispute] = []
    verifier = client.for_role("verifier")
    try:
        verify_response = verifier.generate(
            verify_messages,
            response_schema=VerifierReview,
            prompt_version=PROMPT_VERSION,
        )
        review: VerifierReview = verify_response.parsed
        for item in review.reviews:
            if item.stance == "agree" or item.finding_id not in finding_index:
                continue
            key, text = finding_index[item.finding_id]
            disputes.append(
                Dispute(
                    finding_id=item.finding_id,
                    perspective=key,
                    finding=text,
                    stance=item.stance,
                    verifier_reason=item.reason,
                )
            )
        _save(
            ipo_id=ipo_id,
            run_id=run_id,
            kind="verification",
            output={"reviews": [r.model_dump() for r in review.reviews]},
            response=verify_response,
            messages=verify_messages,
            db_path=db_path,
        )
    except LLMError as exc:
        notes.append(f"verifier unavailable: {exc}")

    # 4. Challenge (optional) ----------------------------------------------
    stage("challenge")
    challenger = client.for_role("challenger")
    challenger_used = False
    if disputes and challenger.enabled:
        dispute_text = "\n".join(
            f"[{d.finding_id}] Finding: {d.finding}\n    Verifier ({d.stance}): "
            f"{d.verifier_reason}"
            for d in disputes
        )
        challenge_messages = [
            LLMMessage("system", CHALLENGER_SYSTEM),
            LLMMessage(
                "user",
                f"IPO: {name}\n\nDisputes:\n{dispute_text}\n\nEvidence:\n{facts_text}",
            ),
        ]
        try:
            challenge_response = challenger.generate(
                challenge_messages,
                response_schema=ChallengerReview,
                prompt_version=PROMPT_VERSION,
            )
            rulings = {r.finding_id: r for r in challenge_response.parsed.rulings}
            disputes = [
                d.model_copy(
                    update={
                        "ruling": rulings[d.finding_id].ruling,
                        "ruling_reason": rulings[d.finding_id].reason,
                    }
                )
                if d.finding_id in rulings
                else d
                for d in disputes
            ]
            challenger_used = True
            _save(
                ipo_id=ipo_id,
                run_id=run_id,
                kind="challenge",
                output=challenge_response.parsed,
                response=challenge_response,
                messages=challenge_messages,
                db_path=db_path,
            )
        except LLMError as exc:
            notes.append(f"challenger unavailable: {exc}")
    elif disputes:
        notes.append("challenger not configured; disputes left unresolved")

    _save(
        ipo_id=ipo_id,
        run_id=run_id,
        kind="disputes",
        output={"disputes": [d.model_dump() for d in disputes]},
        response=None,
        messages=None,
        db_path=db_path,
    )

    # 5. Synthesis (H5) -----------------------------------------------------
    stage("synthesis")
    perspective_text = "\n\n".join(
        f"{p.key.upper()} {p.title} (confidence {p.confidence.level}): "
        f"{p.conclusion}\n"
        + "\n".join(f"- {e.point} [{', '.join(e.fact_ids)}]" for e in p.evidence)
        + (
            "\nMissing: " + "; ".join(p.missing_information)
            if p.missing_information
            else ""
        )
        for p in perspectives
        if not p.error
    )
    dispute_lines = (
        "\n".join(
            f"- [{d.finding_id}] {d.finding} — verifier: {d.stance} ({d.verifier_reason});"
            f" ruling: {d.ruling}"
            for d in disputes
        )
        or "- none"
    )
    deterministic = (
        json.dumps(
            {
                key: analysis.get(key)
                for key in ("score", "verdict", "strengths", "risks", "data_gaps")
            },
            default=str,
        )
        if analysis
        else "not computed (run `analyze`)"
    )
    synthesis_messages = [
        LLMMessage("system", SYNTHESIS_SYSTEM),
        LLMMessage(
            "user",
            f"IPO: {name}\n\nPerspectives:\n{perspective_text}\n\n"
            f"Dispute log:\n{dispute_lines}\n\n"
            f"Deterministic screening result: {deterministic}",
        ),
    ]
    synthesis_response = analyst.generate(
        synthesis_messages, response_schema=Assessment, prompt_version=PROMPT_VERSION
    )
    assessment: Assessment = synthesis_response.parsed
    _save(
        ipo_id=ipo_id,
        run_id=run_id,
        kind="h5",
        output={**assessment.model_dump(), "notes": notes},
        response=synthesis_response,
        messages=synthesis_messages,
        db_path=db_path,
        confidence=assessment.confidence.level,
    )

    return ResearchResult(
        run_id=run_id,
        fact_pack=pack,
        perspectives=perspectives,
        disputes=disputes,
        assessment=assessment,
        challenger_used=challenger_used,
        notes=notes,
    )


__all__ = [
    "ResearchError",
    "ResearchResult",
    "STAGES",
    "apply_citation_gate",
    "run_research",
]
