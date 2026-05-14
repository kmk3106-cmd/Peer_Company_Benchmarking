"""DI817305 / DI818100 / DI818105 / DI818200 / DI818205 일괄 서베이.

각 role × 8개사:
- 보고 fact 수
- 별도 보고 여부
- TOP 3 element + ko_label
"""
from __future__ import annotations
import duckdb

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
ROLES = [
    ("DI817305", "보험계약 정보 (잔액)"),
    ("DI818100", "보험계약 위험관리 (변동/지표)"),
    ("DI818105", "보험계약 위험관리 (잔액)"),
    ("DI818200", "위험관리 상세 (변동/지표)"),
    ("DI818205", "위험관리 상세 (잔액)"),
]

CONS_AXIS = "ifrs-full_ConsolidatedAndSeparateFinancialStatementsAxis"
SEP = "ifrs-full_SeparateMember"

con = duckdb.connect("data/db/benchmark.duckdb", read_only=True)


def role_summary(cik, role_code):
    role_id = f"dart_2024-06-30_role-{role_code}"
    sql = f"""
    SELECT
      (SELECT COUNT(*) FROM val_insurers v
        JOIN pre_insurers p USING (CIK, ELEMENT_ID)
        WHERE v.CIK=? AND p.ROLE_ID=? AND v.amount_krw IS NOT NULL) AS n_facts,
      (SELECT COUNT(*) FROM val_insurers v
        JOIN pre_insurers p USING (CIK, ELEMENT_ID)
        WHERE v.CIK=? AND p.ROLE_ID=? AND v.amount_krw IS NOT NULL
          AND EXISTS (SELECT 1 FROM cntxt_insurers cx
            WHERE cx.CIK=v.CIK AND cx.REPORT_DATE=v.REPORT_DATE AND cx.CONTEXT_ID=v.CONTEXT_ID
              AND cx.AXIS_ELEMENT_ID='{CONS_AXIS}' AND cx.MEMBER_ELEMENT_ID='{SEP}')) AS n_sep
    """
    n_facts, n_sep = con.execute(sql, [cik, role_id, cik, role_id]).fetchone()
    if n_facts == 0:
        return n_facts, n_sep, []
    # TOP 3 element
    top = con.execute("""
      SELECT v.ELEMENT_ID, MAX(CASE WHEN l.LANG='ko' THEN l.LABEL END) AS ko, COUNT(*) AS n
      FROM val_insurers v
      JOIN pre_insurers p USING (CIK, ELEMENT_ID)
      LEFT JOIN lab_insurers l ON l.CIK=v.CIK AND l.ELMT_ID=v.ELEMENT_ID
      WHERE v.CIK=? AND p.ROLE_ID=? AND v.amount_krw IS NOT NULL
      GROUP BY v.ELEMENT_ID ORDER BY n DESC LIMIT 3
    """, [cik, role_id]).fetchall()
    return n_facts, n_sep, top


for role_code, role_label in ROLES:
    print("="*100)
    print(f"  {role_code} — {role_label}")
    print("="*100)
    print(f"\n  {'회사':<14s}  {'전체 facts':>10s}  {'별도':>10s}  TOP element")
    print("─"*100)
    any_reported = False
    for cik, name in PEERS:
        n_facts, n_sep, top = role_summary(cik, role_code)
        if n_facts == 0:
            print(f"  {name:<12s}  {'미보고':>10s}")
            continue
        any_reported = True
        top_str = ""
        if top:
            eid, ko, n = top[0]
            ko_short = (ko or "")[:38]
            top_str = f"{n:>4d} ({ko_short})"
        print(f"  {name:<12s}  {n_facts:>10,d}  {n_sep:>10,d}  {top_str}")

    if not any_reported:
        print(f"\n  ⚠ {role_code}: 8개사 모두 미보고")
    print()
