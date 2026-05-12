"""Stream a quarterly DART XBRL zip into a DuckDB database.

Tables created (raw, all VARCHAR):
    sub_raw, txn_raw, txn_dts_raw, elmt_raw, role_raw, pre_raw, def_raw,
    cal_raw, lab_raw, cntxt_raw, val_raw

Views created:
    val_norm           — val_raw + amount_krw column (DECIMALS-normalized KRW)
    val_insurers       — val_norm filtered to 11 KOSPI-listed insurers
    role_insurers, lab_insurers, cntxt_insurers

Idempotent: re-running drops and re-creates raw tables. Views are CREATE OR REPLACE.
"""

from __future__ import annotations

import argparse
import logging
import shutil
import zipfile
from collections.abc import Iterable
from pathlib import Path

import duckdb

log = logging.getLogger(__name__)

# All 11 TSV files in the DART XBRL zip
TSV_FILES = (
    "sub.tsv",
    "txn.tsv",
    "txn-dts.tsv",
    "elmt.tsv",
    "role.tsv",
    "pre.tsv",
    "def.tsv",
    "cal.tsv",
    "lab.tsv",
    "cntxt.tsv",
    "val.tsv",
)

# 11 KOSPI-listed Korean insurers — from data/ref/companies.csv
INSURER_CIKS = (
    "00112332",  # 미래에셋생명 (self)
    "00126256",  # 삼성생명
    "00113058",  # 한화생명
    "00117267",  # 동양생명
    "00139214",  # 삼성화재
    "00164973",  # 현대해상
    "00159102",  # DB손해보험
    "00135917",  # 한화손해보험
    "00113562",  # 롯데손해보험
    "00103176",  # 흥국화재
    "00113191",  # 코리안리
)


def _table_name(tsv: str) -> str:
    """Map a TSV filename to its raw DuckDB table name (dash→underscore + _raw)."""
    base = tsv.removesuffix(".tsv").replace("-", "_")
    return f"{base}_raw"


def extract_one(zip_path: Path, tsv_name: str, dest_dir: Path) -> Path | None:
    """Extract a single TSV from zip. Returns target path, or None if not in zip.

    Skips if target exists and size matches the zip entry (idempotent).
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    target = dest_dir / tsv_name
    with zipfile.ZipFile(zip_path) as zf:
        try:
            info = zf.getinfo(tsv_name)
        except KeyError:
            return None
        if target.exists() and target.stat().st_size == info.file_size:
            log.info("  skip extract (size match): %s", tsv_name)
            return target
        log.info("  extracting %s (%.1f MB) ...", tsv_name, info.file_size / 1024 / 1024)
        with zf.open(tsv_name) as src, target.open("wb") as dst:
            shutil.copyfileobj(src, dst, length=4 * 1024 * 1024)
    return target


def load_tsv(con: duckdb.DuckDBPyConnection, tsv_path: Path, table: str) -> int:
    """Replace `table` with the full content of tsv_path. Returns row count.

    Options matter for the messy real-world TSVs:
    - all_varchar=true: no type inference on a 2.9GB file
    - quote='' : DART claims to strip special chars but val.tsv has stray '"'
                  inside VALUE cells (e.g., '"신용스왑'). Disabling quote treats
                  '"' as a normal char so a stray one doesn't capture multi-MB
                  blocks across newlines.
    - escape='' : pair with quote to disable escape processing
    - strict_mode=false: tolerate minor RFC4180 violations
    """
    con.execute(f"DROP TABLE IF EXISTS {table}")
    con.execute(
        f"CREATE TABLE {table} AS "
        f"SELECT * FROM read_csv(?, delim='\t', header=true, all_varchar=true, "
        f"sample_size=-1, quote='', escape='', strict_mode=false)",
        [str(tsv_path)],
    )
    return con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]


def stream_load_quarter(
    con: duckdb.DuckDBPyConnection,
    zip_path: Path | None,
    raw_dir: Path,
    delete_after: bool = True,
) -> dict[str, int]:
    """For each TSV: extract (if zip given) → load → optionally delete the TSV.

    This keeps peak disk usage ≈ size of the single biggest TSV (val.tsv ≈ 2.9GB),
    avoiding the 13GB peak of fully unpacking first.
    """
    counts: dict[str, int] = {}
    for tsv in TSV_FILES:
        log.info("--- %s ---", tsv)
        if zip_path is not None:
            path = extract_one(zip_path, tsv, raw_dir)
            if path is None:
                log.warning("  zip missing %s — skipping", tsv)
                continue
        else:
            path = raw_dir / tsv
            if not path.exists():
                log.warning("  missing %s — skipping", path)
                continue

        table = _table_name(tsv)
        size_mb = path.stat().st_size / 1024 / 1024
        log.info("  loading → %s (%.1f MB)...", table, size_mb)
        n = load_tsv(con, path, table)
        counts[table] = n
        log.info("  -> %s rows", f"{n:,}")

        if delete_after:
            try:
                path.unlink()
                log.info("  deleted raw TSV (freed %.1f MB)", size_mb)
            except OSError as e:
                log.warning("  could not delete %s: %s", path, e)
    return counts


def create_normalized_views(con: duckdb.DuckDBPyConnection) -> None:
    """Build val_norm: val_raw with a typed amount_krw column.

    Per XBRL 2.1 spec, the DECIMALS attribute denotes *precision* (the value is
    accurate to 10^DECIMALS units), NOT a unit scaler. VALUE is always given in
    the unit named by UNIT_ID. We verified with real DART data:
      - 흥국화재 자산 raw=12,894,689,000,000 with DECIMALS=-6 → 12.89조원 ✓
      - 미래에셋생명 자산 raw=32,404,438,804,746 with DECIMALS=0 → 32.4조원 ✓
    So amount_krw = VALUE itself when UNIT_ID='KRW', regardless of DECIMALS.

    Notes:
      - val.tsv header is ELEMENT_ID (the spec PDF says ELMT_ID; data wins)
      - lab.tsv uses ELMT_ID — different column name, must reconcile on join
    """
    con.execute("""
        CREATE OR REPLACE VIEW val_norm AS
        SELECT
          CIK,
          REPORT_DATE,
          ELEMENT_ID,
          TAXONOMY_ID,
          CONTEXT_ID,
          UNIT_ID,
          DECIMALS,                       -- kept as precision metadata only
          VALUE AS raw_value,
          CASE
            WHEN UNIT_ID = 'KRW'
                 AND TRY_CAST(VALUE AS DOUBLE) IS NOT NULL
              THEN TRY_CAST(VALUE AS DOUBLE)
            ELSE NULL
          END AS amount_krw
        FROM val_raw
    """)


def create_insurer_views(
    con: duckdb.DuckDBPyConnection,
    ciks: Iterable[str] = INSURER_CIKS,
) -> None:
    """Create CIK-filtered views for the 11 insurers — common query starting point."""
    cik_list = ", ".join(f"'{c}'" for c in ciks)
    for src, view in [
        ("val_norm", "val_insurers"),
        ("role_raw", "role_insurers"),
        ("lab_raw", "lab_insurers"),
        ("cntxt_raw", "cntxt_insurers"),
        ("pre_raw", "pre_insurers"),
        ("def_raw", "def_insurers"),
        ("cal_raw", "cal_insurers"),
    ]:
        con.execute(
            f"CREATE OR REPLACE VIEW {view} AS "
            f"SELECT * FROM {src} WHERE CIK IN ({cik_list})"
        )


def validate(con: duckdb.DuckDBPyConnection) -> dict:
    """Run integrity / coverage checks. Returns a dict for logging."""
    out: dict = {}
    out["n_submissions"] = con.execute("SELECT count(*) FROM sub_raw").fetchone()[0]
    out["unique_ciks"] = con.execute("SELECT count(DISTINCT CIK) FROM sub_raw").fetchone()[0]
    out["val_rows"] = con.execute("SELECT count(*) FROM val_raw").fetchone()[0]
    out["insurer_val_rows"] = con.execute("SELECT count(*) FROM val_insurers").fetchone()[0]
    out["insurer_amount_non_null"] = con.execute(
        "SELECT count(*) FROM val_insurers WHERE amount_krw IS NOT NULL"
    ).fetchone()[0]
    out["unit_distribution"] = con.execute(
        "SELECT UNIT_ID, count(*) FROM val_raw GROUP BY UNIT_ID ORDER BY 2 DESC LIMIT 10"
    ).fetchall()
    out["decimals_distribution_krw"] = con.execute(
        "SELECT DECIMALS, count(*) FROM val_raw WHERE UNIT_ID='KRW' "
        "GROUP BY DECIMALS ORDER BY 2 DESC LIMIT 10"
    ).fetchall()
    out["insurer_role_counts"] = con.execute("""
        SELECT CIK, count(DISTINCT ROLE_ID) AS n_roles
        FROM role_insurers
        GROUP BY CIK
        ORDER BY CIK
    """).fetchall()
    out["insurer_ifrs17_role_counts"] = con.execute("""
        SELECT CIK, count(DISTINCT ROLE_ID) AS n_ifrs17_roles
        FROM role_insurers
        WHERE ROLE_ID LIKE '%DI817%' OR ROLE_ID LIKE '%DI818%'
        GROUP BY CIK
        ORDER BY CIK
    """).fetchall()
    return out


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("quarter", help="quarter label, e.g. 2025Q4")
    parser.add_argument("--zip", type=Path, help="path to zip; if omitted, expects pre-extracted TSVs")
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("data/db/benchmark.duckdb"),
        help="DuckDB file path (default: data/db/benchmark.duckdb)",
    )
    parser.add_argument(
        "--raw-root",
        type=Path,
        default=Path("data/raw"),
        help="root for extracted TSV folders (default: data/raw)",
    )
    parser.add_argument(
        "--keep-raw",
        action="store_true",
        help="do not delete TSV files after loading (default: delete to save disk)",
    )
    args = parser.parse_args(argv)

    raw_dir = args.raw_root / args.quarter

    if args.zip and not args.zip.exists():
        log.error("zip not found: %s", args.zip)
        return 2

    if args.zip is None and (not raw_dir.exists() or not any(raw_dir.glob("*.tsv"))):
        log.error("no TSVs in %s and no --zip given", raw_dir)
        return 2

    args.db.parent.mkdir(parents=True, exist_ok=True)
    log.info("=== Phase 2: streaming extract+load into %s ===", args.db)
    con = duckdb.connect(str(args.db))

    counts = stream_load_quarter(
        con,
        zip_path=args.zip,
        raw_dir=raw_dir,
        delete_after=not args.keep_raw,
    )
    log.info("=== Phase 2c: building normalized views ===")
    create_normalized_views(con)
    create_insurer_views(con)

    log.info("=== Phase 2d: validation ===")
    summary = validate(con)
    con.close()

    print("\n=== Load summary ===")
    for k, v in counts.items():
        print(f"  {k:14s} {v:>14,} rows")
    print("\n=== Validation ===")
    for k, v in summary.items():
        if isinstance(v, list):
            print(f"  {k}:")
            for row in v:
                print(f"    {row}")
        else:
            print(f"  {k}: {v}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
