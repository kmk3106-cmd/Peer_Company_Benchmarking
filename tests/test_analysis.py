"""Analysis library tests.

These hit the real DuckDB if it exists; skipped otherwise so the suite stays
green on fresh clones.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from peer_benchmarking.analysis import cross_section, measurement_model, ratios
from peer_benchmarking.analysis.queries import QuerySpec

DB_PATH = Path(__file__).parent.parent / "data" / "db" / "benchmark.duckdb"
HAS_DB = DB_PATH.exists() and DB_PATH.stat().st_size > 1_000_000


@pytest.fixture(scope="module")
def con():
    if not HAS_DB:
        pytest.skip("benchmark.duckdb not present — run Phase 2 ingest first")
    c = duckdb.connect(str(DB_PATH), read_only=True)
    yield c
    c.close()


@pytest.fixture
def spec():
    # Project rule: 별도(separate) 기준 default (CLAUDE.md §7)
    return QuerySpec(report_date="20251231", consolidation="separate", peer_group="all_insurers")


def test_liability_balance_returns_all_peers(con, spec):
    df = cross_section.liability_balance(con, spec, item_name="total_liability")
    assert not df.empty
    # Should have a row for at least most of the 11 peers
    assert len(df) >= 9
    # Sample sanity: 삼성생명 should be > 100조원
    samsung = df[df["cik"] == "00126256"]
    assert not samsung.empty
    assert samsung["amount_krw"].iloc[0] > 1e14  # > 100조원


def test_component_decomposition_has_three_components(con, spec):
    df = cross_section.component_decomposition(con, spec)
    assert not df.empty
    components = set(df["component"].unique())
    assert components == {"BEL", "RA", "CSM"}


def test_pl_insurance_revenue(con, spec):
    df = cross_section.pl_item(
        con,
        spec,
        item_name="insurance_revenue",
        period_start="2025-01-01",
        period_end="2025-12-31",
    )
    # Should resolve for most insurers
    assert len(df) >= 5
    assert (df["amount_krw"] > 0).all()


def test_model_share_paa_vs_nonpaa(con, spec):
    df = measurement_model.model_share(con, spec)
    assert not df.empty
    # Each row should have shares summing to 1.0 (when total > 0)
    for _, row in df.iterrows():
        if row["total"] > 0:
            assert abs(row["paa_share"] + row["nonpaa_share"] - 1.0) < 1e-6


def test_self_percentile_includes_mirae(con, spec):
    df = cross_section.liability_balance(con, spec, item_name="total_liability")
    result = ratios.self_percentile(df)
    assert result["cik"] == "00112332"
    assert result["name_ko"] == "미래에셋생명"
    assert 0 <= result["percentile"] <= 100
    assert 1 <= result["rank"] <= result["n_peers"]


def test_summarize_panel_is_json_serializable(con, spec):
    import json

    df = cross_section.liability_balance(con, spec, item_name="total_liability")
    bundle = ratios.summarize_panel(df, label="보험계약부채")
    # Round-trip through JSON — fails if any NaN/Inf/datetime leaks through
    rebuilt = json.loads(json.dumps(bundle, default=str))
    assert rebuilt["label"] == "보험계약부채"
    assert "self" in rebuilt
    assert isinstance(rebuilt["rows"], list)
