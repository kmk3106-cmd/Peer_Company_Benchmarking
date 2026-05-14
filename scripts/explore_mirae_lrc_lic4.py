"""LRC/LIC × dart_Life|Other × Issued × Separate 의 실제 element 별 값.

2025-12-31 instant 및 2025년 duration 전수 dump.
"""
from __future__ import annotations
import duckdb, pandas as pd

pd.set_option("display.width", 240)
pd.set_option("display.max_colwidth", 90)
pd.set_option("display.max_rows", 200)

CIK = "00112332"
SEP = "ifrs-full_SeparateMember"
ISSUED = "ifrs-full_InsuranceContractsIssuedMember"
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
    ANY_VALUE(cx.PERIOD_START_DATE) AS pstart,
    ANY_VALUE(cx.PERIOD_END_DATE) AS pend,
    ANY_VALUE(cx.PERIOD_INSTANT) AS pinst
  FROM cntxt_insurers cx
  WHERE cx.CIK='{CIK}'
  GROUP BY cx.CONTEXT_ID
)
SELECT v.ELEMENT_ID, c.lrclic, c.types,
       c.pstart, c.pend, c.pinst,
       v.amount_krw / 1e12 AS amt_조,
       v.amount_krw
FROM val_insurers v
JOIN ctx c USING (CONTEXT_ID)
WHERE v.CIK='{CIK}'
  AND v.amount_krw IS NOT NULL
  AND c.cons='{SEP}'
  AND c.disagg='{ISSUED}'
  AND c.lrclic IS NOT NULL
  AND c.types IN ('dart_LifeInsuranceMember', 'dart_OtherInsuranceMember')
  AND (c.pinst IN ('2024-12-31','2025-12-31') OR (c.pstart='2025-01-01' AND c.pend='2025-12-31'))
ORDER BY v.ELEMENT_ID, c.types, c.lrclic, c.pinst NULLS LAST, c.pend
"""
df = con.execute(sql).df()
df["elem"] = df["ELEMENT_ID"].str.replace("ifrs-full_", "").str.replace("dart_", "d:").str.replace("entity00112332_", "#").str[:70]
df["lrclic_s"] = df["lrclic"].str.replace("ifrs-full_", "").str.replace("Member", "")
df["types_s"] = df["types"].str.replace("dart_", "d:").str.replace("Member", "")
df["period"] = df.apply(lambda r: r["pinst"] if pd.notna(r["pinst"]) else f"{r['pstart']}~{r['pend']}", axis=1)
print(df[["elem", "lrclic_s", "types_s", "period", "amt_조"]].to_string(index=False))
