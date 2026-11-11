"""Tests for the FastAPI service using a temporary database."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.main import create_app
from src.config import LLMSettings
from src.database import db
from src.models.ipo import IPO
from src.utils.normalization import normalize_name


def make_ipo(name: str, *, gmp_percent: float, status: str = "Open") -> IPO:
    return IPO(
        name=name,
        normalized_name=normalize_name(name),
        category="SME",
        status=status,
        issue_price=100.0,
        issue_price_lower=95.0,
        issue_price_upper=100.0,
        estimated_listing_price=100.0 + gmp_percent,
        ipo_size_cr="50.00",
        sector="Packaging",
        exchange="NSE",
        subscription=3.0,
        pe=20.0,
        open_date="2026-01-01",
        close_date="2099-01-01",
        gmp=gmp_percent,
        gmp_percent=gmp_percent,
    )


@pytest.fixture
def client(tmp_path):
    db_path = tmp_path / "test.db"
    report_dir = tmp_path / "reports"

    db.save_ipo_with_gmp(
        make_ipo("Above Ltd", gmp_percent=30),
        "test",
        db_path=db_path,
    )
    db.save_ipo_with_gmp(
        make_ipo("Below Ltd", gmp_percent=5),
        "test",
        db_path=db_path,
    )
    db.save_ipo_with_gmp(
        make_ipo("Sunrise Packaging", gmp_percent=22),
        "test",
        db_path=db_path,
    )
    db.save_ipo_with_gmp(
        make_ipo("Sunrise Packagings", gmp_percent=22),
        "test",
        db_path=db_path,
    )
    db.save_ipo_with_gmp(
        make_ipo("Listed Ltd", gmp_percent=40, status="Listed"),
        "test",
        db_path=db_path,
    )

    app = create_app(
        db_path=db_path,
        report_dir=report_dir,
        api_token="test-token",
        # Pin AI off so a developer's .env (LLM_ENABLED=true) cannot make
        # tests reach a real model runtime.
        llm_settings=LLMSettings(),
    )

    with TestClient(app) as test_client:
        yield test_client


def test_health(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["database"].endswith("test.db")

    ai = payload["ai"]
    assert ai["enabled"] is False
    assert ai["available"] is False
    assert "LLM_ENABLED=false" in ai["detail"]
    assert ai["provider"]
    assert ai["model"]


def test_list_ipos_paginates_and_counts(client):
    response = client.get("/api/ipos", params={"limit": 2, "offset": 0})

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 5
    assert len(payload["items"]) == 2
    assert payload["limit"] == 2
    assert payload["offset"] == 0


def test_list_ipos_filters_by_min_gmp(client):
    response = client.get("/api/ipos", params={"min_gmp": 20})

    assert response.status_code == 200
    names = {item["name"] for item in response.json()["items"]}
    assert names == {"Above Ltd", "Sunrise Packaging", "Sunrise Packagings", "Listed Ltd"}


def test_list_ipos_filters_by_status(client):
    response = client.get(
        "/api/ipos",
        params={"status": "Open", "min_gmp": 20},
    )

    assert response.status_code == 200
    names = {item["name"] for item in response.json()["items"]}
    assert names == {"Above Ltd", "Sunrise Packaging", "Sunrise Packagings"}


def test_list_ipos_searches_name_case_insensitively(client):
    response = client.get("/api/ipos", params={"q": "SUNRISE"})

    assert response.status_code == 200
    payload = response.json()
    names = {item["name"] for item in payload["items"]}
    assert names == {"Sunrise Packaging", "Sunrise Packagings"}
    assert payload["total"] == 2


def test_list_ipos_sorts_by_gmp_descending(client):
    response = client.get(
        "/api/ipos",
        params={"sort": "gmp_percent", "order": "desc"},
    )

    assert response.status_code == 200
    percents = [item["gmp_percent"] for item in response.json()["items"]]
    assert percents == sorted(percents, reverse=True)


def test_list_ipos_defaults_to_name_ascending(client):
    response = client.get("/api/ipos")

    assert response.status_code == 200
    names = [item["name"] for item in response.json()["items"]]
    assert names == sorted(names)


def test_list_ipos_rejects_unknown_sort_field(client):
    response = client.get("/api/ipos", params={"sort": "gmp_percent; DROP TABLE ipos"})

    assert response.status_code == 422


def test_get_ipo_includes_history(client):
    listing = client.get("/api/ipos", params={"status": "Open"}).json()
    ipo_id = next(
        item["id"] for item in listing["items"] if item["name"] == "Above Ltd"
    )

    response = client.get(f"/api/ipos/{ipo_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "Above Ltd"
    assert payload["gmp_percent"] == 30
    assert len(payload["gmp_history"]) == 1
    assert payload["gmp_history"][0]["source"] == "test"
    assert payload["sources"][0]["source"] == "test"
    assert payload["sources"][0]["source_url"] is None


def test_get_missing_ipo_returns_404(client):
    response = client.get("/api/ipos/99999")
    assert response.status_code == 404


def test_candidates_exclude_listed_ipos(client):
    response = client.get("/api/candidates", params={"min_gmp": 20})

    assert response.status_code == 200
    names = {item["name"] for item in response.json()}
    assert names == {"Above Ltd", "Sunrise Packaging", "Sunrise Packagings"}


def test_analyze_requires_token(client):
    response = client.post("/api/analyze", json={"persist": False})
    assert response.status_code == 401


def test_analyze_with_token_persists(client):
    response = client.post(
        "/api/analyze",
        json={"persist": True, "min_gmp_percent": 20},
        headers={"X-API-Token": "test-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 3
    assert payload["analyses"][0]["name"]

    listing = client.get("/api/ipos", params={"status": "Open"}).json()
    ipo_id = next(
        item["id"] for item in listing["items"] if item["name"] == "Above Ltd"
    )
    detail = client.get(f"/api/ipos/{ipo_id}").json()
    assert detail["latest_analysis"]["name"] == "Above Ltd"


def test_report_requires_token(client):
    response = client.post("/api/reports", json={"min_gmp_percent": 20})
    assert response.status_code == 401


def test_report_create_list_and_download(client):
    created = client.post(
        "/api/reports",
        json={"min_gmp_percent": 20},
        headers={"X-API-Token": "test-token"},
    )

    assert created.status_code == 200
    info = created.json()
    assert info["filename"].endswith(".pdf")
    assert info["size_bytes"] > 1000

    listed = client.get("/api/reports")
    assert listed.status_code == 200
    assert any(item["filename"] == info["filename"] for item in listed.json())

    download = client.get(info["download_url"])
    assert download.status_code == 200
    assert download.content.startswith(b"%PDF")


def test_missing_report_returns_404(client):
    response = client.get("/api/reports/does-not-exist.pdf")
    assert response.status_code == 404


def test_possible_duplicates(client):
    response = client.get("/api/quality/duplicates", params={"threshold": 90})

    assert response.status_code == 200
    pairs = response.json()
    names = {
        (pair["first_name"], pair["second_name"]) for pair in pairs
    }
    assert ("Sunrise Packaging", "Sunrise Packagings") in names
