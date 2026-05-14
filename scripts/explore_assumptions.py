"""IFRS17 계리적 가정 변동 element 탐색.

탐색 대상:
- 할인율 변경 효과 (DiscountRate)
- 금융가정 변경 (FinancialAssumption)
- 비금융위험 가정 변경 (NonFinancialRisk)
- 위험율 가정 (RiskRate)
- 해지율 가정 (CancellationRate / LapseRate)
- 손실요소 (Loss Component)
- 신계약 (NewContract)
- CSM 상각 element
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

ASSUMPTION_KEYWORDS = [
    "할인율", "DiscountRate", "할인률",
    "금융가정", "FinancialAssumption",
    "비금융위험", "NonFinancial",
    "위험율", "RiskRate",
    "해지율", "CancellationRate", "LapseRate",
    "손실요소", "LossComponent", "LossFactor",
    "신계약", "NewContract", "InitiallyRecognised",
    "환율변동", "ForeignExchange",
    "투자가정", "InvestmentAssumption",
    "사업비가정", "ExpenseAssumption",
    "유지비가정",
    "추정치", "Estimate",
    "가정변경", "AssumptionChange",
]

con = duckdb.connect("data/db/benchmark.duckdb", read_only=True)

# 핵심 element pattern 별로 8개사 보유 여부 매트릭스
PATTERNS_TO_CHECK = [
    ("할인율 변경 효과", ["%ChangeEffectOfDiscountRate%", "%할인%", "%DiscountRate%"]),
    ("금융가정 변경", ["%FinancialAssumption%", "%금융가정%"]),
    ("위험율 가정변경", ["%RiskRate%Assumption%", "%위험율%가정%", "%RiskRateAssumption%"]),
    ("해지율 가정변경", ["%CancellationRate%Assumption%", "%LapseRate%", "%해지율%가정%", "%CancellationRateAssumption%"]),
    ("유지비 가정변경", ["%유지비%가정%", "%MaintenanceExpense%Change%", "%ExpenseAssumption%"]),
    ("손실요소 인식·환입", ["%LossComponent%Recognised%", "%손실요소%", "%LossFactor%"]),
    ("신계약 효과", ["%EffectsOfContractsInitiallyRecognised%", "%NewContract%"]),
    ("환율변동 효과", ["%ChangesInForeignExchangeRates%", "%환율변동%"]),
    ("투자가정 변경", ["%투자가정%", "%InvestmentAssumption%"]),
    ("CSM 상각 (보험수익)", ["%InsuranceRevenueContractualServiceMargin%", "%RecognitionOfContractualServiceMargin%"]),
]

print("="*100)
print("8개사 × 가정 변동 element 보유 매트릭스")
print("="*100)
print(f"\n  {'가정 변동 항목':<22s}  " + "  ".join(f"{n[:5]:>6s}" for _, n in PEERS))
print("─"*100)

for label, patterns in PATTERNS_TO_CHECK:
    counts = {}
    for cik, name in PEERS:
        or_parts = " OR ".join("v.ELEMENT_ID LIKE ?" for _ in patterns)
        sql = f"""
        SELECT COUNT(DISTINCT v.ELEMENT_ID) FROM val_insurers v
        WHERE v.CIK=? AND v.amount_krw IS NOT NULL AND ({or_parts})
        """
        n = con.execute(sql, [cik] + patterns).fetchone()[0]
        counts[cik] = n
    cells = ["✓" if counts[c] > 0 else "·" for c, _ in PEERS]
    print(f"  {label:<22s}  " + "  ".join(f"{c:>6s}" for c in cells))

# Step 2: 각 회사별 가정 관련 element 풀 dump (TOP 5)
print("\n\n" + "="*100)
print("회사별 가정 관련 element TOP 5 (entity 확장 포함)")
print("="*100)

for cik, name in PEERS:
    print(f"\n  ── {name} ──")
    # 가정 변경 관련 element 찾기
    keywords_or = " OR ".join(
        "l.LABEL LIKE ? OR v.ELEMENT_ID LIKE ?"
        for _ in ASSUMPTION_KEYWORDS
    )
    params = [cik]
    for kw in ASSUMPTION_KEYWORDS:
        params.extend([f"%{kw}%", f"%{kw}%"])
    sql = f"""
    SELECT DISTINCT v.ELEMENT_ID,
           MAX(CASE WHEN l.LANG='ko' THEN l.LABEL END) AS ko,
           COUNT(*) AS n
    FROM val_insurers v
    JOIN pre_insurers p ON p.CIK=v.CIK AND p.ELEMENT_ID=v.ELEMENT_ID
    LEFT JOIN lab_insurers l ON l.CIK=v.CIK AND l.ELMT_ID=v.ELEMENT_ID
    WHERE v.CIK=? AND v.amount_krw IS NOT NULL
      AND p.ROLE_ID='dart_2024-06-30_role-DI817100'
      AND ({keywords_or})
    GROUP BY v.ELEMENT_ID ORDER BY n DESC LIMIT 8
    """
    rows = con.execute(sql, params).fetchall()
    for eid, ko, n in rows:
        eshort = eid.replace("ifrs-full_","").replace("dart_","d:").replace(f"entity{cik}_","#")[:55]
        print(f"    [{n:>4d}] {eshort:<57s} ← {ko or ''}")
