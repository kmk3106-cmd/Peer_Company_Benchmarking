"""확장 search — 7개사 (미래에셋 외) 의 가정변경·추정변동 표 search.

미래에셋은 'ChangesInInsuranceLiabilitiesBasedOnActuarialAssumptions' 사용.
다른 회사들은 같은 element 없지만 비슷한 표 있을 가능성.

확장 키워드:
- 가정변경, 가정의 변경
- 추정의 변경, 추정치 변동
- AssumptionChange, EstimateChange
"""
from __future__ import annotations
import duckdb

PEERS = [
    ("00126256", "삼성생명"),
    ("00113058", "한화생명"),
    ("00117267", "동양생명"),
    ("00139214", "삼성화재"),
    ("00164973", "현대해상"),
    ("00159102", "DB손보"),
    ("00135917", "한화손보"),
]

EXTENDED_KEYWORDS = [
    "가정의 변경", "가정 변경", "가정변경",
    "AssumptionChange", "ChangesInAssumption", "ChangingAssumption",
    "추정의 변경", "추정변경",
    "보험부채 변동내역", "보험계약부채 변동내역",
    "ChangesInInsuranceLiabilities",
    "EffectOfChangingAssumption",
]

con = duckdb.connect("data/db/benchmark.duckdb", read_only=True)

for cik, name in PEERS:
    print(f"\n{'='*100}")
    print(f"  {name} ({cik}) — 확장 search")
    print(f"{'='*100}")
    found = False
    for kw in EXTENDED_KEYWORDS:
        rows = con.execute("""
          SELECT DISTINCT l.ELMT_ID, l.LABEL,
                 (SELECT COUNT(*) FROM val_insurers v WHERE v.CIK=l.CIK AND v.ELEMENT_ID=l.ELMT_ID AND v.amount_krw IS NOT NULL) AS n_facts
          FROM lab_insurers l
          WHERE l.CIK=? AND l.LANG='ko' AND (l.LABEL LIKE ? OR l.ELMT_ID LIKE ?)
        """, [cik, f"%{kw}%", f"%{kw}%"]).fetchall()
        rows = [r for r in rows if r[2] > 0]  # fact 있는 것만
        if rows:
            found = True
            print(f"\n  키워드 '{kw}' — {len(rows)}개 매치 (fact 있음):")
            for eid, label, n in rows[:5]:
                eshort = eid.replace("ifrs-full_","").replace("dart_","d:").replace(f"entity{cik}_","#")[:62]
                print(f"    [{n:>4d}] {eshort:<64s} ← {label[:55]}")
    if not found:
        print(f"  ❌ 모든 키워드 매치 없음")
