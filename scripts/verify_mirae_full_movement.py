"""미래에셋 보험계약부채 변동 검증 — 사용자 disclosure 좌측표(LRC+LIC, BEL+RA+CSM 합산)와 매칭."""
from __future__ import annotations
import duckdb

CIK = "00112332"
SEP = "ifrs-full_SeparateMember"
ISSUED = "ifrs-full_InsuranceContractsIssuedMember"

con = duckdb.connect("data/db/benchmark.duckdb", read_only=True)

# 변동표 21-1 role(DI817105 별도) 소속 element만, Sep × Issued, 위험관리 sub-table 멤버 제외
SQL = """
WITH ko AS (
  SELECT ELMT_ID, MIN(LABEL) AS LABEL FROM lab_insurers
  WHERE CIK=? AND REPORT_DATE='20251231' AND LANG='ko' GROUP BY ELMT_ID
),
mv_elems AS (
  SELECT DISTINCT ELEMENT_ID FROM pre_insurers
  WHERE CIK=? AND REPORT_DATE='20251231' AND ROLE_ID='dart_2024-06-30_role-DI817105'
),
ctxs AS (
  SELECT CONTEXT_ID,
         MAX(PERIOD_INSTANT) AS p_inst,
         MAX(PERIOD_START_DATE) AS p_start,
         MAX(PERIOD_END_DATE) AS p_end
  FROM cntxt_insurers WHERE CIK=? AND REPORT_DATE='20251231'
  GROUP BY CONTEXT_ID
  HAVING BOOL_OR(MEMBER_ELEMENT_ID = ?)   -- Separate
     AND BOOL_OR(MEMBER_ELEMENT_ID = ?)   -- Issued
     AND NOT BOOL_OR(MEMBER_ELEMENT_ID LIKE '%OfDisclosureOfNatureAndExtentOfRisks%')
     AND NOT BOOL_OR(AXIS_ELEMENT_ID = 'ifrs-full_InsuranceContractsByComponentsAxis')  -- 컴포넌트 분해 없는 합계
)
SELECT
  CASE WHEN c.p_inst='2024-12-31' THEN 'opening'
       WHEN c.p_inst='2025-12-31' THEN 'closing'
       WHEN c.p_start='2025-01-01' AND c.p_end='2025-12-31' THEN 'duration'
       ELSE NULL END,
  v.ELEMENT_ID, COALESCE(ko.LABEL,''),
  SUM(v.amount_krw)/1e8 AS amt_eok,
  COUNT(*) AS n
FROM val_insurers v
JOIN ctxs c USING(CONTEXT_ID)
JOIN mv_elems me ON me.ELEMENT_ID=v.ELEMENT_ID
LEFT JOIN ko ON ko.ELMT_ID=v.ELEMENT_ID
WHERE v.CIK=? AND v.REPORT_DATE='20251231' AND v.amount_krw IS NOT NULL
  AND (c.p_inst IN ('2024-12-31','2025-12-31')
       OR (c.p_start='2025-01-01' AND c.p_end='2025-12-31'))
GROUP BY 1, v.ELEMENT_ID, ko.LABEL
HAVING SUM(v.amount_krw) IS NOT NULL
ORDER BY 1, ABS(SUM(v.amount_krw)) DESC
"""

rows = con.execute(SQL, [CIK, CIK, CIK, SEP, ISSUED, CIK]).fetchall()

# 사용자 disclosure 좌측표 (LRC+LIC 합산, 모든 컴포넌트, 별도, 발행)
USER = {
    "기초 부채":              262_484_118_353.53,  # 26,248,411,835,353원 / 1e8
    "보험수익":               -10_804.12,
    "발생한 보험금 등":       5_926.27,
    "보험취득CF 상각":        2_188.64,
    "발생사고요소 조정":      195.85,
    "손실부담계약 손실(환입)": 667.10,
    "투자요소 및 보험료환급": 0,
    "수취한 보험료":          40_500.28,
    "보험취득CF 지급":        -5_948.34,
    "보험금/서비스비용 지급": -42_969.50,
    "당기손익 금융손익":      22_727.79,
    "기타포괄 금융손익":      -4_834.72,
    "기타증감":               -166.38,
    "자산 기말":              0,
    "부채 기말":              269_966.98,
}
# 원/억 단위 보정
USER["기초 부채"] = 26_248_411_835_353 / 1e8
USER["부채 기말"] = 26_996_698_255_523 / 1e8

print("="*100)
print("미래에셋 별도 변동표 — 좌측표(LRC+LIC, 모든 컴포넌트) 사용자 disclosure vs XBRL 추출")
print("="*100)
print(f"\n[Period kind 분류]")
counts = {}
for kind, eid, lbl, amt, n in rows:
    counts[kind] = counts.get(kind, 0) + 1
print(counts)

print(f"\n[기초 잔액]")
for kind, eid, lbl, amt, n in rows:
    if kind == "opening":
        print(f"  {amt:>+15,.0f}억  [n={n}]  {lbl[:40]:<40s} | {eid[:60]}")
print(f"  사용자 disclosure 기초 = {USER['기초 부채']:+,.0f}억")

print(f"\n[기말 잔액]")
for kind, eid, lbl, amt, n in rows:
    if kind == "closing":
        print(f"  {amt:>+15,.0f}억  [n={n}]  {lbl[:40]:<40s} | {eid[:60]}")
print(f"  사용자 disclosure 기말 = {USER['부채 기말']:+,.0f}억")

print(f"\n[변동 lines (FY2025)]")
for kind, eid, lbl, amt, n in rows:
    if kind == "duration":
        print(f"  {amt:>+15,.0f}억  [n={n}]  {lbl[:55]:<55s} | {eid[:50]}")

print(f"\n[사용자 disclosure 변동]")
for k, v in list(USER.items())[1:13]:
    print(f"  {v:>+15,.0f}억  {k}")
