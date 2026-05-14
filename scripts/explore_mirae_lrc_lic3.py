"""미래에셋 DI817100: 별도·발행보험·2025 — LRC/LIC × (TypesOfContracts) 풀 분포."""
from __future__ import annotations
import duckdb, pandas as pd

CIK = "00112332"
ROLE = "dart_2024-06-30_role-DI817100"
LRC_LIC_AXIS = "ifrs-full_InsuranceContractsByRemainingCoverageAndIncurredClaimsAxis"
TYPES_AXIS = "ifrs-full_TypesOfContractsAxis"
CONS_AXIS = "ifrs-full_ConsolidatedAndSeparateFinancialStatementsAxis"
DISAGG_AXIS = "ifrs-full_DisaggregationOfInsuranceContractsAxis"
SEP = "ifrs-full_SeparateMember"
ISSUED = "ifrs-full_InsuranceContractsIssuedMember"

con = duckdb.connect("data/db/benchmark.duckdb", read_only=True)

# context attributes:
#   has_lrclic_mem (LRC_excl/LC/LIC),
#   has_types_mem (사망/건강/연금/저축/...),
#   n_axes_total,
#   period (instant or duration with start/end)

print("=== 별도·발행·2025 context: LRC/LIC × TypesOfContracts × movement element ===")
sql = f"""
WITH role_ctx AS (
  SELECT DISTINCT v.CONTEXT_ID
  FROM val_insurers v JOIN pre_insurers p USING (CIK, ELEMENT_ID)
  WHERE p.CIK=? AND p.ROLE_ID=? AND v.amount_krw IS NOT NULL
),
attr AS (
  SELECT cx.CONTEXT_ID,
    MAX(CASE WHEN cx.AXIS_ELEMENT_ID='{LRC_LIC_AXIS}' THEN cx.MEMBER_ELEMENT_ID END) AS lrclic,
    MAX(CASE WHEN cx.AXIS_ELEMENT_ID='{TYPES_AXIS}' THEN cx.MEMBER_ELEMENT_ID END) AS types,
    MAX(CASE WHEN cx.AXIS_ELEMENT_ID='{CONS_AXIS}' THEN cx.MEMBER_ELEMENT_ID END) AS cons,
    MAX(CASE WHEN cx.AXIS_ELEMENT_ID='{DISAGG_AXIS}' THEN cx.MEMBER_ELEMENT_ID END) AS disagg,
    COUNT(*) AS n_axes,
    ANY_VALUE(cx.PERIOD_START_DATE) AS pstart,
    ANY_VALUE(cx.PERIOD_END_DATE) AS pend,
    ANY_VALUE(cx.PERIOD_INSTANT) AS pinst
  FROM cntxt_insurers cx
  WHERE cx.CIK=? AND cx.CONTEXT_ID IN (SELECT CONTEXT_ID FROM role_ctx)
  GROUP BY cx.CONTEXT_ID
)
SELECT lrclic, types, disagg,
       COUNT(*) AS n_ctx, MIN(n_axes) AS min_ax, MAX(n_axes) AS max_ax
FROM attr
WHERE cons='{SEP}' AND lrclic IS NOT NULL
GROUP BY lrclic, types, disagg
ORDER BY lrclic, types, disagg
"""
df = con.execute(sql, [CIK, ROLE, CIK]).df()
print(df.to_string(index=False))
