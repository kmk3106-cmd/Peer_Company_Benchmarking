"""해약환급금준비금·보증준비금 (기적립·적립예정) 추출.

전략: 표준 dart element 먼저, 없으면 axis 분해 (RetainedEarnings × ReserveMember) 후순위.
"""
from __future__ import annotations
import duckdb, json
from pathlib import Path

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

# 별도 멤버 조건
SEP = "ifrs-full_SeparateMember"

DIRECT_SQL = """
SELECT v.amount_krw/1e8
FROM val_insurers v JOIN cntxt_insurers c USING(CIK, REPORT_DATE, CONTEXT_ID)
WHERE v.CIK=? AND v.REPORT_DATE='20251231' AND v.ELEMENT_ID=?
  AND EXISTS(SELECT 1 FROM cntxt_insurers c2 WHERE c2.CIK=v.CIK AND c2.REPORT_DATE=v.REPORT_DATE
             AND c2.CONTEXT_ID=v.CONTEXT_ID AND c2.MEMBER_ELEMENT_ID=?)
  AND v.amount_krw IS NOT NULL
ORDER BY ABS(v.amount_krw) DESC LIMIT 1
"""

AXIS_SQL = """
SELECT v.amount_krw/1e8
FROM val_insurers v JOIN cntxt_insurers c USING(CIK, REPORT_DATE, CONTEXT_ID)
WHERE v.CIK=? AND v.REPORT_DATE='20251231' AND v.ELEMENT_ID=?
  AND c.MEMBER_ELEMENT_ID=?
  AND v.amount_krw IS NOT NULL
ORDER BY ABS(v.amount_krw) DESC LIMIT 1
"""

def fetch_pair(cik, direct_eid, axis_eid, axis_member):
    # 1) 표준 element (별도 필터)
    r = con.execute(DIRECT_SQL, [cik, direct_eid, SEP]).fetchone()
    if r and r[0] is not None: return r[0]
    # 2) 별도 필터 없이
    r = con.execute("""
        SELECT SUM(v.amount_krw)/1e8 FROM val_insurers v
        WHERE v.CIK=? AND v.REPORT_DATE='20251231' AND v.ELEMENT_ID=? AND v.amount_krw IS NOT NULL
    """, [cik, direct_eid]).fetchone()
    if r and r[0] is not None: return r[0]
    # 3) axis-based
    r = con.execute(AXIS_SQL, [cik, axis_eid, axis_member]).fetchone()
    return r[0] if r else None


def f(v): return f"{v:>+10,.0f}억" if v is not None else "         -"
hdr = f"  {'회사':<14s}  {'해약기적립':>12s}  {'해약적립예정':>12s}  {'보증기적립':>12s}  {'보증적립예정':>12s}"
print(hdr); print("-"*len(hdr))
results = {}
for cik, name in PEERS:
    sb = fetch_pair(cik, "dart_SurrenderValueReserve",        "ifrs-full_RetainedEarnings",              "dart_SurrenderValueReserveMember")
    sa = fetch_pair(cik, "dart_SurrenderValueReserveToBeAdded","dart_RegulatoryReserveToBeAddedReversed", "dart_SurrenderValueReserveMember")
    gb = fetch_pair(cik, "dart_GuranteeReserve",              "ifrs-full_RetainedEarnings",              "dart_GuaranteeReserveMember")
    ga = fetch_pair(cik, "dart_GuranteeReserveToBeAdded",     "dart_RegulatoryReserveToBeAddedReversed", "dart_GuaranteeReserveMember")
    results[cik] = {"name": name, "sur_bal": sb, "sur_add": sa, "gua_bal": gb, "gua_add": ga}
    print(f"  {name:<14s}  {f(sb)}  {f(sa)}  {f(gb)}  {f(ga)}")

Path("report/surrender_guarantee_reserves.json").write_text(
    json.dumps(results, ensure_ascii=False, indent=2, default=lambda v: float(v) if v else None),
    encoding="utf-8")
print("\nwrote report/surrender_guarantee_reserves.json")
