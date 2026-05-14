"""미래에셋 DI817100 — 사망 (dart_Life) × LRC/LIC × 별도·발행 전수 검토.

목적: 어떤 element가 어떤 라벨로 보고되는지, 값과 함께 모두 dump.
"""
from __future__ import annotations
import duckdb, pandas as pd

pd.set_option("display.width", 260)
pd.set_option("display.max_colwidth", 100)
pd.set_option("display.max_rows", 300)

CIK = "00112332"
LRC_LIC_AXIS = "ifrs-full_InsuranceContractsByRemainingCoverageAndIncurredClaimsAxis"
TYPES_AXIS = "ifrs-full_TypesOfContractsAxis"
CONS_AXIS = "ifrs-full_ConsolidatedAndSeparateFinancialStatementsAxis"
DISAGG_AXIS = "ifrs-full_DisaggregationOfInsuranceContractsAxis"

con = duckdb.connect("data/db/benchmark.duckdb", read_only=True)

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
       c.lrclic, c.n_axes,
       v.amount_krw / 1e8 AS amt_억,
       (CASE WHEN c.pinst IS NOT NULL THEN c.pinst
             ELSE c.pstart || '~' || c.pend END) AS period
FROM val_insurers v
JOIN ctx c USING (CONTEXT_ID)
LEFT JOIN lab_insurers l ON l.CIK=v.CIK AND l.ELMT_ID=v.ELEMENT_ID
WHERE v.CIK='{CIK}'
  AND v.amount_krw IS NOT NULL
  AND c.cons='ifrs-full_SeparateMember'
  AND c.disagg='ifrs-full_InsuranceContractsIssuedMember'
  AND c.lrclic IS NOT NULL
  AND c.types='dart_LifeInsuranceMember'
  AND (c.pinst IN ('2024-12-31','2025-12-31') OR (c.pstart='2025-01-01' AND c.pend='2025-12-31'))
GROUP BY v.ELEMENT_ID, c.lrclic, c.n_axes, v.amount_krw, c.pinst, c.pstart, c.pend
ORDER BY v.ELEMENT_ID, period, c.lrclic
"""
df = con.execute(sql).df()
df["elem_short"] = df["ELEMENT_ID"].str.replace("ifrs-full_", "").str.replace("dart_", "d:").str.replace("entity00112332_", "#").str[:75]
df["lrclic_s"] = df["lrclic"].str.replace("ifrs-full_", "").str.replace("Member", "").str[:50]
print(df[["elem_short", "ko_label", "lrclic_s", "n_axes", "period", "amt_억"]].to_string(index=False))
