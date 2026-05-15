"""8개사 「보험계약마진 미조정 추정변동」 × RA component 정확 추출."""
from __future__ import annotations
import json
import duckdb
from peer_benchmarking.analysis.fact_fetcher import (
    fetch_fact_sum, FactQuery, CONS_AXIS, SEP_MEMBER, DISAGG_AXIS, ISSUED_MEMBER,
    COMPONENTS_AXIS, COMP_RA, COMP_BEL, COMP_CSM_ALL,
)

PEERS = [
    ("00112332", "미래에셋생명"),
    ("00126256", "삼성생명"),
    ("00113058", "한화생명"),
    ("00117267", "동양생명"),
    ("00139214", "삼성화재"),
    ("00164973", "현대해상"),
    ("00159102", "DB손해보험"),
    ("00135917", "한화손해보험"),
]

con = duckdb.connect("data/db/benchmark.duckdb", read_only=True)
PAT = "%ChangesInEstimatesThatDoNotAdjustContractualServiceMargin%"


def fetch(cik, comp_member=None, with_issued=True):
    eid = con.execute("""
      SELECT v.ELEMENT_ID FROM val_insurers v
      WHERE v.CIK=? AND v.ELEMENT_ID LIKE ?
      LIMIT 1
    """, [cik, PAT]).fetchone()
    if not eid: return None
    req = {CONS_AXIS: SEP_MEMBER}
    if with_issued:
        req[DISAGG_AXIS] = ISSUED_MEMBER
    if comp_member:
        req[COMPONENTS_AXIS] = comp_member
    return fetch_fact_sum(con, FactQuery(
        cik=cik, report_date="20251231", element_id=eid[0],
        required_members=req, period_range=("2025-01-01", "2025-12-31"),
    ))


print(f"  {'회사':<14s}  {'BEL':>10s}  {'RA':>10s}  {'CSM(전체)':>12s}  {'합계':>10s}  ← 별도+발행")
print("─"*80)
results = {}
for cik, name in PEERS:
    bel = fetch(cik, COMP_BEL)
    ra = fetch(cik, COMP_RA)
    csm = 0; csm_found = False
    for m in COMP_CSM_ALL:
        v = fetch(cik, m)
        if v is not None: csm += v; csm_found = True
    csm = csm if csm_found else None
    total_no_axis = fetch(cik)  # axis 없이 (broader)
    def f(v): return f"{v/1e8:>+8,.0f}억" if v is not None else "         —"
    print(f"  {name:<12s}  {f(bel)}  {f(ra)}  {f(csm)}  {f(total_no_axis)}")
    results[cik] = {"name": name, "BEL": bel, "RA": ra, "CSM": csm, "total": total_no_axis}

from pathlib import Path
Path("report/csm_not_adjust_components.json").write_text(
    json.dumps(results, ensure_ascii=False, indent=2, default=lambda v: float(v) if v else None),
    encoding="utf-8")
print(f"\nwrote report/csm_not_adjust_components.json")
