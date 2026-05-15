"""Discover BEL movement elements for each peer in DI817105 role.

For each peer, list elements that appear in pre_insurers role DI817105,
get Sep × Issued (non-component, non-risk) value, and print per period kind.
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
SEP = "ifrs-full_SeparateMember"
ISSUED = "ifrs-full_InsuranceContractsIssuedMember"
ROLE = "dart_2024-06-30_role-DI817105"

con = duckdb.connect("data/db/benchmark.duckdb", read_only=True)

SQL = """
WITH ko AS (
  SELECT ELMT_ID, MIN(LABEL) AS LABEL FROM lab_insurers
  WHERE CIK=? AND REPORT_DATE='20251231' AND LANG='ko' GROUP BY ELMT_ID
),
mv_elems AS (
  SELECT DISTINCT ELEMENT_ID FROM pre_insurers
  WHERE CIK=? AND REPORT_DATE='20251231' AND ROLE_ID=?
),
ctxs AS (
  SELECT CONTEXT_ID,
         COUNT(*) AS n_ax,
         MAX(PERIOD_INSTANT) AS p_inst,
         MAX(PERIOD_START_DATE) AS p_start,
         MAX(PERIOD_END_DATE) AS p_end
  FROM cntxt_insurers WHERE CIK=? AND REPORT_DATE='20251231'
  GROUP BY CONTEXT_ID
  HAVING BOOL_OR(MEMBER_ELEMENT_ID = ?)
     AND BOOL_OR(MEMBER_ELEMENT_ID = ?)
     AND NOT BOOL_OR(MEMBER_ELEMENT_ID LIKE '%OfDisclosureOfNatureAndExtentOfRisks%')
     AND NOT BOOL_OR(AXIS_ELEMENT_ID = 'ifrs-full_InsuranceContractsByComponentsAxis')
),
fact AS (
  SELECT v.ELEMENT_ID, c.n_ax,
         CASE WHEN c.p_inst='2024-12-31' THEN 'opening'
              WHEN c.p_inst='2025-12-31' THEN 'closing'
              WHEN c.p_start='2025-01-01' AND c.p_end='2025-12-31' THEN 'duration'
              ELSE NULL END AS pk,
         v.amount_krw
  FROM val_insurers v JOIN ctxs c USING(CONTEXT_ID)
  WHERE v.CIK=? AND v.REPORT_DATE='20251231' AND v.amount_krw IS NOT NULL
),
top_each AS (
  SELECT ELEMENT_ID, pk, MIN(n_ax) AS min_ax FROM fact WHERE pk IS NOT NULL GROUP BY ELEMENT_ID, pk
)
SELECT f.pk, f.ELEMENT_ID, COALESCE(ko.LABEL,'') AS LABEL,
       SUM(f.amount_krw)/1e8 AS amt_eok,
       COUNT(*) AS n
FROM fact f JOIN top_each t USING(ELEMENT_ID, pk)
JOIN mv_elems me ON me.ELEMENT_ID=f.ELEMENT_ID
LEFT JOIN ko ON ko.ELMT_ID=f.ELEMENT_ID
WHERE f.n_ax = t.min_ax AND f.pk IS NOT NULL
GROUP BY f.pk, f.ELEMENT_ID, ko.LABEL
HAVING SUM(f.amount_krw) IS NOT NULL
ORDER BY f.pk, ABS(SUM(f.amount_krw)) DESC
"""

for cik, name in PEERS:
    print("="*120)
    print(f"{name} ({cik})")
    print("="*120)
    rows = con.execute(SQL, [cik, cik, ROLE, cik, SEP, ISSUED, cik]).fetchall()
    if not rows:
        print("  (DI817105 role 데이터 없음)")
        continue
    cur_pk = None
    for pk, eid, lbl, amt, n in rows:
        if pk != cur_pk:
            print(f"\n  [{pk}]")
            cur_pk = pk
        print(f"    {amt:>+15,.0f}억  [n={n}]  {lbl[:50]:<50s}  | {eid[:60]}")
