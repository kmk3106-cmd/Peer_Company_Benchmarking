"""Phase 1 sanity check — environment and package imports work."""

from __future__ import annotations


def test_package_imports():
    import peer_benchmarking

    assert peer_benchmarking.__version__ == "0.1.0"


def test_subpackages_importable():
    from peer_benchmarking import analysis, domain, ingest, render  # noqa: F401


def test_core_dependencies_present():
    import duckdb
    import openpyxl  # noqa: F401
    import pandas  # noqa: F401
    import plotly  # noqa: F401
    import polars  # noqa: F401
    import yaml  # noqa: F401

    # DuckDB sanity: in-memory query works
    con = duckdb.connect(":memory:")
    result = con.execute("SELECT 1 AS n").fetchone()
    assert result == (1,)
    con.close()


def test_companies_csv_loadable():
    import csv
    from pathlib import Path

    csv_path = Path(__file__).parent.parent / "data" / "ref" / "companies.csv"
    assert csv_path.exists(), f"missing {csv_path}"

    with csv_path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 14, f"expected 14 insurers (8 life + 6 non-life), got {len(rows)}"
    ciks = {r["cik"] for r in rows}
    assert "00112332" in ciks, "self CIK 00112332 (미래에셋생명) missing"

    self_rows = [r for r in rows if r["is_self"] == "true"]
    assert len(self_rows) == 1, "exactly one self entry expected"
    assert self_rows[0]["name_ko"] == "미래에셋생명"


def test_peer_groups_yaml_loadable():
    from pathlib import Path

    import yaml

    yml_path = Path(__file__).parent.parent / "data" / "ref" / "peer_groups.yml"
    with yml_path.open(encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    assert cfg["self_cik"] == "00112332"
    assert {"all_insurers", "life", "non_life", "ifrs17_detailed"} <= set(cfg["groups"])
    assert len(cfg["groups"]["all_insurers"]["members"]) == 14
    assert len(cfg["groups"]["life"]["members"]) == 8
