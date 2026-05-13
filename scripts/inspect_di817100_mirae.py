"""미래에셋생명 DI817100 (보험계약부채 변동분 차이조정) 검증용 dump.

출력: report/mirae_DI817100.xlsx
  시트 1: 구성요소별 (BEL/RA/CSM)
  시트 2: LRC/LIC별
  시트 3: raw_all — 모든 element + context 펼침 (사업보고서 직접 대조용)
"""

from __future__ import annotations

import logging
from pathlib import Path

import duckdb
import pandas as pd

from peer_benchmarking.analysis.movement_reconciliation import (
    MovementSpec,
    fetch_movement_raw,
    filter_consolidation,
    pivot_by_components,
    pivot_by_lrc_lic,
)

CIK = "00112332"
log = logging.getLogger(__name__)


def _readable(df: pd.DataFrame) -> pd.DataFrame:
    """Strip ifrs-full_/dart_/entity prefixes in identifier columns."""
    if df.empty:
        return df
    out = df.copy()
    for col in ("element_id", "members", "axis_members"):
        if col in out.columns:
            out[col + "_short"] = (
                out[col]
                .fillna("")
                .str.replace("ifrs-full_", "", regex=False)
                .str.replace("dart-gcd_", "", regex=False)
                .str.replace("dart_", "d:", regex=False)
                .str.replace("entity00112332_", "#", regex=False)
            )
    return out


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    db_path = Path("data/db/benchmark.duckdb")
    out = Path("report/mirae_DI817100.xlsx")
    out.parent.mkdir(parents=True, exist_ok=True)

    spec = MovementSpec(cik=CIK)
    con = duckdb.connect(str(db_path), read_only=True)

    log.info("fetching raw movement rows ...")
    raw = fetch_movement_raw(con, spec)
    raw_sep = filter_consolidation(raw, spec)
    log.info("  raw rows                 : %s", f"{len(raw):,}")
    log.info("  filtered (별도)          : %s", f"{len(raw_sep):,}")

    log.info("building components pivot (BEL/RA/CSM) ...")
    comp_pivot = pivot_by_components(con, spec)
    log.info("  components pivot rows    : %s", len(comp_pivot))

    log.info("building LRC/LIC pivot ...")
    lrc_pivot = pivot_by_lrc_lic(con, spec)
    log.info("  lrc_lic pivot rows       : %s", len(lrc_pivot))

    con.close()

    # Cosmetic: trillion-won column for human readability
    def _add_trillion(df: pd.DataFrame, cols) -> pd.DataFrame:
        if df.empty:
            return df
        for c in cols:
            if c in df.columns:
                df[f"{c}(조)"] = (df[c] / 1e12).round(3)
        return df

    comp_disp = _add_trillion(comp_pivot.copy(), ["BEL", "RA", "CSM", "합계"])
    lrc_disp = _add_trillion(
        lrc_pivot.copy(),
        [c for c in lrc_pivot.columns if c not in ("element_id", "ko_label", "bucket")],
    )
    raw_disp = _readable(raw_sep)
    raw_disp["amount(조)"] = (raw_disp["amount_krw"] / 1e12).round(4)
    raw_cols = [
        "element_id_short", "ko_label", "members_short",
        "period_start", "period_end", "period_instant",
        "amount(조)", "amount_krw", "decimals", "element_id", "axis_members_short",
    ]

    log.info("writing %s ...", out)
    with pd.ExcelWriter(out, engine="openpyxl") as xw:
        comp_disp.to_excel(xw, sheet_name="구성요소(BEL_RA_CSM)", index=False)
        lrc_disp.to_excel(xw, sheet_name="LRC_LIC", index=False)
        raw_disp[raw_cols].to_excel(xw, sheet_name="raw_all", index=False)

    log.info("done: %s (%.1f KB)", out, out.stat().st_size / 1024)

    # CLI summary: 시작/종료 잔액 + 주요 변동
    print()
    print("=" * 80)
    print("미래에셋생명 보험계약부채 변동분 차이조정 — 구성요소별 (별도, 2025)")
    print("=" * 80)
    if not comp_disp.empty:
        # show the rows with non-trivial total
        focus = comp_disp[comp_disp["합계"].fillna(0).abs() > 1e10].copy()
        focus = focus.sort_values("bucket")
        for _, r in focus.iterrows():
            label = (r["ko_label"] or "")[:38] or r["element_id"][:38]
            bel = f"{r['BEL']/1e12:+,.2f}조" if pd.notna(r["BEL"]) else "      -"
            ra = f"{r['RA']/1e12:+,.2f}조" if pd.notna(r["RA"]) else "      -"
            csm = f"{r['CSM']/1e12:+,.2f}조" if pd.notna(r["CSM"]) else "      -"
            tot = f"{r['합계']/1e12:+,.2f}조" if pd.notna(r["합계"]) else "      -"
            bucket = r["bucket"][:32]
            print(f"  [{bucket:32s}] {label:38s} BEL={bel} RA={ra} CSM={csm} 합={tot}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
