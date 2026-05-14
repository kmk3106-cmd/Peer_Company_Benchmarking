"""사업비 영역 — DART XBRL에서 사업비 관련 element 탐색.

탐색 키워드:
- 사업비 (operating expense, business expense)
- 신계약비 (acquisition cost)
- 유지비 (maintenance)
- 사업비율 (expense ratio)
- 사업비 분석 (expense analysis)

대상 role:
- DI220000/005: 손익계산서
- DI817400/405: 보험서비스결과 (보험수익·서비스비용)
- DI817305: 보험계약 정보 (예정/예상유지비)
- DI820000+: 사업비 별도 role (있을 경우)
"""
from __future__ import annotations
import duckdb

PEERS = [
    ("00112332", "미래에셋"),
    ("00126256", "삼성생명"),
    ("00113058", "한화생명"),
    ("00117267", "동양생명"),
    ("00139214", "삼성화재"),
    ("00164973", "현대해상"),
    ("00159102", "DB손보"),
    ("00135917", "한화손보"),
]

# 사업비 관련 키워드
EXPENSE_KEYWORDS = [
    "사업비", "유지비", "신계약비", "취득비", "관리비", "운영비",
    "OperatingExpense", "AcquisitionCost", "MaintenanceExpense",
    "AdministrativeExpense", "OperatingCost",
]

con = duckdb.connect("data/db/benchmark.duckdb", read_only=True)

print("="*100)
print("STEP 1: 회사별 사업비 관련 element 탐색 (TOP 8)")
print("="*100)

for cik, name in PEERS:
    where_parts = ["l.LABEL LIKE ? OR v.ELEMENT_ID LIKE ?" for _ in EXPENSE_KEYWORDS]
    params = [cik]
    for kw in EXPENSE_KEYWORDS:
        params.extend([f"%{kw}%", f"%{kw}%"])
    sql = f"""
    SELECT v.ELEMENT_ID,
           MAX(CASE WHEN l.LANG='ko' THEN l.LABEL END) AS ko,
           COUNT(*) AS n,
           MIN(p.ROLE_ID) AS role
    FROM val_insurers v
    LEFT JOIN lab_insurers l ON l.CIK=v.CIK AND l.ELMT_ID=v.ELEMENT_ID
    LEFT JOIN pre_insurers p ON p.CIK=v.CIK AND p.ELEMENT_ID=v.ELEMENT_ID
    WHERE v.CIK=? AND v.amount_krw IS NOT NULL
      AND ({" OR ".join(where_parts)})
    GROUP BY v.ELEMENT_ID
    ORDER BY n DESC LIMIT 8
    """
    rows = con.execute(sql, params).fetchall()
    print(f"\n  ── {name} ── ({len(rows)} 후보)")
    for eid, ko, n, role in rows:
        eshort = eid.replace("ifrs-full_", "").replace("dart_", "d:").replace(f"entity{cik}_", "#")[:55]
        role_short = role.split("role-")[-1][:10] if role else ""
        print(f"    [{n:>5d}] {eshort:<57s} ← {ko or ''}  [{role_short}]")

# Step 2: 회사 모두 공통 사업비 라인 확인
print("\n\n" + "="*100)
print("STEP 2: 공통 사업비 element (3개사 이상 보고)")
print("="*100)

sql_common = f"""
SELECT v.ELEMENT_ID,
       MAX(CASE WHEN l.LANG='ko' THEN l.LABEL END) AS ko,
       COUNT(DISTINCT v.CIK) AS n_companies,
       COUNT(*) AS n_facts
FROM val_insurers v
LEFT JOIN lab_insurers l ON l.CIK=v.CIK AND l.ELMT_ID=v.ELEMENT_ID
WHERE v.CIK IN ({",".join("'"+c+"'" for c, _ in PEERS)})
  AND v.amount_krw IS NOT NULL
  AND ({" OR ".join("v.ELEMENT_ID LIKE ?" for _ in EXPENSE_KEYWORDS)})
GROUP BY v.ELEMENT_ID
HAVING n_companies >= 3
ORDER BY n_companies DESC, n_facts DESC
LIMIT 20
"""
common_rows = con.execute(sql_common, [f"%{kw}%" for kw in EXPENSE_KEYWORDS]).fetchall()
print(f"\n  {'element':<60s}  {'회사수':>6s}  {'fact수':>7s}  ko_label")
print("─"*120)
for eid, ko, n_c, n_f in common_rows:
    eshort = eid.replace("ifrs-full_", "")[:58]
    print(f"  {eshort:<60s}  {n_c:>5d}/8  {n_f:>7,d}  {ko or ''}")
