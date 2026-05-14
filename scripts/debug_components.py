"""미래에셋 BEL/RA/CSM 잔액 검증 — context 전수 dump.

확인: 27조 = BEL + RA + CSM 이 맞아야 함.
"""
from __future__ import annotations
import duckdb

CIK = "00112332"
COMPONENTS_AXIS = "ifrs-full_InsuranceContractsByComponentsAxis"
CONS_AXIS = "ifrs-full_ConsolidatedAndSeparateFinancialStatementsAxis"
SEP = "ifrs-full_SeparateMember"
DISAGG_AXIS = "ifrs-full_DisaggregationOfInsuranceContractsAxis"
ISSUED = "ifrs-full_InsuranceContractsIssuedMember"

con = duckdb.connect("data/db/benchmark.duckdb", read_only=True)

print("="*100)
print("STEP 1: ComponentsAxis 멤버 전체 dump (미래에셋, 2025-12-31, 별도)")
print("="*100)

sql = """
WITH ax AS (
  SELECT cx.CIK, cx.REPORT_DATE, cx.CONTEXT_ID,
    COUNT(*) AS n_axes,
    MAX(CASE WHEN cx.AXIS_ELEMENT_ID=? THEN cx.MEMBER_ELEMENT_ID END) AS comp_member,
    MAX(CASE WHEN cx.AXIS_ELEMENT_ID=? THEN cx.MEMBER_ELEMENT_ID END) AS cons_member,
    MAX(CASE WHEN cx.AXIS_ELEMENT_ID=? THEN cx.MEMBER_ELEMENT_ID END) AS disagg_member,
    STRING_AGG(cx.AXIS_ELEMENT_ID || '=' || cx.MEMBER_ELEMENT_ID, '|'
               ORDER BY cx.AXIS_ELEMENT_ID, cx.MEMBER_ELEMENT_ID) AS fingerprint
  FROM cntxt_insurers cx WHERE cx.CIK=?
  GROUP BY cx.CIK, cx.REPORT_DATE, cx.CONTEXT_ID
)
SELECT v.ELEMENT_ID,
       MAX(CASE WHEN l.LANG='ko' THEN l.LABEL END) AS ko,
       ax.comp_member,
       ax.n_axes,
       v.amount_krw/1e12 AS amt_조
FROM val_insurers v
JOIN ax USING (CIK, REPORT_DATE, CONTEXT_ID)
LEFT JOIN lab_insurers l ON l.CIK=v.CIK AND l.ELMT_ID=v.ELEMENT_ID
WHERE v.CIK=?
  AND v.amount_krw IS NOT NULL
  AND v.ELEMENT_ID IN (
    'ifrs-full_InsuranceContractsThatAreAssets',
    'ifrs-full_InsuranceContractsThatAreLiabilities',
    'ifrs-full_InsuranceContractsIssuedThatAreLiabilities',
    'ifrs-full_InsuranceContractsIssuedThatAreAssets'
  )
  AND ax.comp_member IS NOT NULL
  AND ax.cons_member = ?
  AND EXISTS (SELECT 1 FROM cntxt_insurers p
    WHERE p.CIK=v.CIK AND p.REPORT_DATE=v.REPORT_DATE AND p.CONTEXT_ID=v.CONTEXT_ID
      AND p.PERIOD_INSTANT='2025-12-31')
GROUP BY v.ELEMENT_ID, v.amount_krw, ax.comp_member, ax.n_axes, ax.fingerprint, ax.disagg_member
ORDER BY ax.comp_member, ax.n_axes, v.amount_krw DESC
LIMIT 60
"""
for r in con.execute(sql, [COMPONENTS_AXIS, CONS_AXIS, DISAGG_AXIS, CIK, CIK, SEP]).fetchall():
    eshort = r[0].replace("ifrs-full_", "")[:50]
    comp = (r[2] or "").replace("ifrs-full_","").replace("Member","")[:40]
    print(f"  [{comp:<40s} n={r[3]}]  {r[4]:>8.2f}조  {eshort}")
