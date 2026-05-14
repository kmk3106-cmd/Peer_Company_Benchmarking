"""예실차 v2 — 의미있는 비교.

방법 1: ≤1년 만기 예상보험금 vs 당기 실제발생사고비용
방법 2: 경험조정 (Experience Adjustment) 절대값 + ÷ 보험수익 비율
"""
from __future__ import annotations
import json
from pathlib import Path

# 기존 데이터 활용
matrix = json.loads(Path("report/line_values_matrix.json").read_text(encoding="utf-8"))
acturial = json.loads(Path("report/actuarial_by_year.json").read_text(encoding="utf-8"))
opex = json.loads(Path("report/operating_expense_results.json").read_text(encoding="utf-8"))

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

print("="*110)
print("예실차 v2 — 방법 A: ≤1년 만기 예상보험금 vs 당기 실제발생사고비용 (FY2025)")
print("="*110)
print(f"\n  {'회사':<10s}  {'≤1년 예상보험금':>16s}  {'당기 실제발생사고':>16s}  {'예실차':>12s}  {'실제/예상':>10s}  시그널")
print("─"*110)

for cik, name in PEERS:
    expected_1y = acturial["예상보험금"].get(cik, {}).get("≤1년")
    actual = matrix.get("발생사고비용", {}).get(cik)

    diff = ratio = None
    if expected_1y and actual and abs(expected_1y) > 1e8:
        diff = actual - expected_1y
        ratio = actual / expected_1y * 100

    def f(v): return f"{v/1e8:>12,.0f}억" if v else "        —"
    ratio_s = f"{ratio:>8.1f}%" if ratio else "      —"
    signal = ""
    if ratio is not None:
        if ratio > 110: signal = "⚠ 실제 > 예상 (위험)"
        elif ratio > 100: signal = "실제 ≳ 예상"
        elif ratio > 80: signal = "✓ 실제 ≈ 예상"
        else: signal = "✓ 실제 << 예상 (보수적)"

    print(f"  {name:<8s}  {f(expected_1y)}  {f(actual)}  {f(diff)}  {ratio_s}  {signal}")


print("\n\n" + "="*100)
print("예실차 v2 — 방법 B: 경험조정 (IFRS17 §103) + 보험수익 대비 비율")
print("="*100)
print(f"\n  {'회사':<10s}  {'경험조정':>12s}  {'보험수익':>13s}  {'조정/수익':>10s}  의미")
print("─"*90)

for cik, name in PEERS:
    exp_adj = matrix.get("경험조정", {}).get(cik)
    revenue = opex.get(cik, {}).get("보험수익")

    ratio = None
    if exp_adj is not None and revenue and abs(revenue) > 1e8:
        ratio = exp_adj / revenue * 100

    def f(v): return f"{v/1e8:>+9,.0f}억" if v is not None else "       —"
    ratio_s = f"{ratio:>+8.2f}%" if ratio is not None else "      —"

    meaning = ""
    if exp_adj is not None:
        if exp_adj > 0: meaning = "실제 > 예상 (보험금 더 발생)"
        elif exp_adj < 0: meaning = "실제 < 예상 (보험금 덜 발생, 유리)"
        else: meaning = "일치"

    print(f"  {name:<8s}  {f(exp_adj)}  {f(revenue)}  {ratio_s}  {meaning}")
