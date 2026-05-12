"""CLI entrypoint: build Excel + HTML report.

Usage:
    python -m peer_benchmarking.render
    python -m peer_benchmarking.render --report-date 20251231 \\
           --excel report/2025_annual.xlsx --html report/2025_annual.html
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import duckdb

from peer_benchmarking.render import excel, plotly_html

log = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=Path("data/db/benchmark.duckdb"))
    parser.add_argument("--report-date", default="20251231")
    parser.add_argument("--period-instant", default="2025-12-31")
    parser.add_argument("--period-start", default="2025-01-01")
    parser.add_argument("--period-end", default="2025-12-31")
    parser.add_argument(
        "--excel",
        type=Path,
        default=Path("report/2025_annual.xlsx"),
        help="Excel output (use 'none' to skip)",
    )
    parser.add_argument(
        "--html",
        type=Path,
        default=Path("report/2025_annual.html"),
        help="Plotly HTML output (use 'none' to skip)",
    )
    args = parser.parse_args(argv)

    if not args.db.exists():
        log.error("DuckDB file not found: %s — run `python -m peer_benchmarking.ingest` first", args.db)
        return 2

    con = duckdb.connect(str(args.db), read_only=True)

    if str(args.excel).lower() != "none":
        log.info("building Excel report → %s", args.excel)
        path = excel.build_report(
            con,
            output_path=args.excel,
            report_date=args.report_date,
            period_instant=args.period_instant,
            period_start=args.period_start,
            period_end=args.period_end,
        )
        log.info("  wrote %s (%.1f KB)", path, path.stat().st_size / 1024)

    if str(args.html).lower() != "none":
        log.info("building HTML report → %s", args.html)
        path = plotly_html.build_html_report(
            con,
            output_path=args.html,
            report_date=args.report_date,
            period_instant=args.period_instant,
            period_start=args.period_start,
            period_end=args.period_end,
        )
        log.info("  wrote %s (%.1f KB)", path, path.stat().st_size / 1024)

    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
