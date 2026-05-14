"""DI817100 미래에셋 — 보고기간, 모든 element ko_label, 추가 누락 라인 점검."""
from __future__ import annotations
import duckdb, pandas as pd

pd.set_option("display.width", 300)
pd.set_option("display.max_colwidth", 120)
pd.set_option("display.max_rows", 500)

CIK = "00112332"

con = duckdb.connect("data/db/benchmark.duckdb", read_only=True)

# 1) DI817100 에 보고된 모든 기간 (report_date, period_start/end/instant)
print("=== 1) DB에 적재된 보고기간 ===")
sql = """
SELECT v.REPORT_DATE, c.PERIOD_START_DATE, c.PERIOD_END_DATE, c.PERIOD_INSTANT,
       COUNT(*) AS n
FROM val_insurers v JOIN cntxt_insurers c USING (CIK, REPORT_DATE, CONTEXT_ID)
JOIN pre_insurers p ON p.CIK=v.CIK AND p.ELEMENT_ID=v.ELEMENT_ID
WHERE v.CIK=? AND p.ROLE_ID='dart_2024-06-30_role-DI817100'
GROUP BY 1,2,3,4
ORDER BY 1,2,3,4
"""
df = con.execute(sql, [CIK]).df()
print(df.to_string(index=False))

# 2) 사망 (Life) × 별도·발행 × 2025 → 모든 element (LRC/LIC 유무 무관) ko_label & 값
print("\n\n=== 2) 사망 × 별도·발행 × 2025 — LRC/LIC 무관 모든 element ===")
LRC_LIC_AXIS = "ifrs-full_InsuranceContractsByRemainingCoverageAndIncurredClaimsAxis"
TYPES_AXIS = "ifrs-full_TypesOfContractsAxis"
CONS_AXIS = "ifrs-full_ConsolidatedAndSeparateFinancialStatementsAxis"
DISAGG_AXIS = "ifrs-full_DisaggregationOfInsuranceContractsAxis"

sql = f"""
WITH ctx AS (
  SELECT cx.CONTEXT_ID,
    MAX(CASE WHEN cx.AXIS_ELEMENT_ID='{LRC_LIC_AXIS}' THEN cx.MEMBER_ELEMENT_ID END) AS lrclic,
    MAX(CASE WHEN cx.AXIS_ELEMENT_ID='{TYPES_AXIS}' THEN cx.MEMBER_ELEMENT_ID END) AS types,
    MAX(CASE WHEN cx.AXIS_ELEMENT_ID='{CONS_AXIS}' THEN cx.MEMBER_ELEMENT_ID END) AS cons,
    MAX(CASE WHEN cx.AXIS_ELEMENT_ID='{DISAGG_AXIS}' THEN cx.MEMBER_ELEMENT_ID END) AS disagg,
    COUNT(*) AS n_axes,
    ANY_VALUE(cx.PERIOD_START_DATE) AS pstart,
    ANY_VALUE(cx.PERIOD_END_DATE) AS pend,
    ANY_VALUE(cx.PERIOD_INSTANT) AS pinst
  FROM cntxt_insurers cx WHERE cx.CIK='{CIK}'
  GROUP BY cx.CONTEXT_ID
)
SELECT v.ELEMENT_ID,
       MAX(CASE WHEN l.LANG='ko' THEN l.LABEL END) AS ko_label,
       c.lrclic IS NOT NULL AS has_lrclic,
       c.n_axes,
       SUM(v.amount_krw) / 1e8 AS sum_억,
       (CASE WHEN c.pinst IS NOT NULL THEN c.pinst
             ELSE c.pstart || '~' || c.pend END) AS period
FROM val_insurers v
JOIN ctx c USING (CONTEXT_ID)
LEFT JOIN lab_insurers l ON l.CIK=v.CIK AND l.ELMT_ID=v.ELEMENT_ID
WHERE v.CIK='{CIK}'
  AND v.amount_krw IS NOT NULL
  AND c.cons='ifrs-full_SeparateMember'
  AND c.disagg='ifrs-full_InsuranceContractsIssuedMember'
  AND c.types='dart_LifeInsuranceMember'
  AND (c.pinst IN ('2024-12-31','2025-12-31') OR (c.pstart='2025-01-01' AND c.pend='2025-12-31'))
GROUP BY v.ELEMENT_ID, c.lrclic, c.n_axes, c.pinst, c.pstart, c.pend
ORDER BY ko_label, period, has_lrclic
"""
df2 = con.execute(sql).df()
df2["elem_short"] = df2["ELEMENT_ID"].str.replace("ifrs-full_", "").str.replace("dart_", "d:").str.replace("entity00112332_", "#").str[:65]
print(df2[["ko_label", "elem_short", "has_lrclic", "n_axes", "period", "sum_억"]].to_string(index=False))
