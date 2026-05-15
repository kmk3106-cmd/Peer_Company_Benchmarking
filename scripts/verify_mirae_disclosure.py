"""미래에셋 disclosure 표 17행 검증 — 각 행 라벨을 terseLabel/default 라벨로 검색해서
회사의 element_id 찾고 XBRL 값 추출 → 사용자 disclosure 값과 비교."""
from __future__ import annotations
import duckdb

CIK = "00112332"
SEP = "ifrs-full_SeparateMember"
ISSUED = "ifrs-full_InsuranceContractsIssuedMember"

con = duckdb.connect("data/db/benchmark.duckdb", read_only=True)

# (라벨, 기간kind, 사용자 disclosure 값 원 단위)
DISCLOSURE = [
    ("부채인 보험계약",                                    "opening", 26_248_411_835_353),
    ("보험수익",                                           "duration", -1_080_411_547_554),
    ("발생한 보험금 및 기타 보험서비스비용",                 "duration",   +592_626_787_607),
    ("보험취득현금흐름 상각",                              "duration",   +218_864_437_494),
    ("발생사고요소의 조정",                                "duration",    +19_584_794_969),
    ("손실부담계약 관련 손실(환입)",                        "duration",    +66_710_164_165),
    ("수취한 보험료",                                      "duration", +4_050_027_788_462),
    ("보험취득현금흐름 지급",                              "duration",   -594_834_366_070),
    ("보험금(투자요소 포함) 및 기타보험서비스비용의 지급",  "duration", -4_296_950_166_750),
    ("당기손익인식 보험금융손익",                          "duration", +2_272_778_949_192),
    ("기타포괄손익인식 보험금융손익",                      "duration",   -483_472_446_698),
    ("기타증감",                                           "duration",    -16_637_974_642),
    ("부채인 보험계약",                                    "closing", 26_996_698_255_523),
]

# 라벨→element_id (terseLabel 또는 default 라벨)
def find_eids(cik, label):
    rows = con.execute("""
        SELECT DISTINCT ELMT_ID, LABEL_ROLE_URI
        FROM lab_insurers
        WHERE CIK=? AND REPORT_DATE='20251231' AND LANG='ko'
          AND TRIM(LABEL) = ?
    """, [cik, label]).fetchall()
    # terseLabel 우선
    terse = [r[0] for r in rows if "terseLabel" in (r[1] or "")]
    if terse: return terse
    return [r[0] for r in rows]

# element 값
SQL_VAL = """
WITH ctxs AS (
  SELECT CONTEXT_ID, COUNT(*) AS n_ax,
         MAX(PERIOD_INSTANT) AS p_inst,
         MAX(PERIOD_START_DATE) AS p_start,
         MAX(PERIOD_END_DATE) AS p_end
  FROM cntxt_insurers WHERE CIK=? AND REPORT_DATE='20251231'
  GROUP BY CONTEXT_ID
  HAVING BOOL_OR(MEMBER_ELEMENT_ID = ?) AND BOOL_OR(MEMBER_ELEMENT_ID = ?)
     AND NOT BOOL_OR(MEMBER_ELEMENT_ID LIKE '%OfDisclosureOfNatureAndExtentOfRisks%')
     AND NOT BOOL_OR(AXIS_ELEMENT_ID = 'ifrs-full_InsuranceContractsByComponentsAxis')
),
fact AS (
  SELECT v.ELEMENT_ID, v.amount_krw, c.n_ax,
         CASE WHEN c.p_inst='2024-12-31' THEN 'opening'
              WHEN c.p_inst='2025-12-31' THEN 'closing'
              WHEN c.p_start='2025-01-01' AND c.p_end='2025-12-31' THEN 'duration'
              ELSE NULL END AS pk
  FROM val_insurers v JOIN ctxs c USING(CONTEXT_ID)
  WHERE v.CIK=? AND v.REPORT_DATE='20251231' AND v.ELEMENT_ID=? AND v.amount_krw IS NOT NULL
),
top_only AS (
  SELECT MIN(n_ax) AS min_ax FROM fact WHERE pk=?
)
SELECT SUM(f.amount_krw)
FROM fact f, top_only t
WHERE f.n_ax = t.min_ax AND f.pk = ?
"""

def get_value(cik, eid, pk):
    r = con.execute(SQL_VAL, [cik, SEP, ISSUED, cik, eid, pk, pk]).fetchone()
    return r[0] if r and r[0] is not None else None

print(f"{'라벨':<40s} | {'기간':<8s} | {'사용자 (원)':>18s} | {'XBRL (원)':>18s} | {'차이':>14s} | element_id")
print("-"*180)
for label, pk, user_v in DISCLOSURE:
    eids = find_eids(CIK, label)
    if not eids:
        print(f"{label:<40s} | {pk:<8s} | {user_v:>18,d} | (라벨 매칭 실패) | – | –")
        continue
    # 모든 매칭 element 의 값 합 (보통 1개)
    total = 0; used_eids = []
    for eid in eids:
        v = get_value(CIK, eid, pk)
        if v is not None:
            total += v
            used_eids.append(eid)
    diff = (total - user_v) if total else None
    diff_s = f"{diff:>+14,.0f}" if diff is not None else "–"
    print(f"{label:<40s} | {pk:<8s} | {user_v:>18,d} | {total:>18,.0f} | {diff_s} | {', '.join(e.replace('ifrs-full_','') for e in used_eids)[:90]}")
