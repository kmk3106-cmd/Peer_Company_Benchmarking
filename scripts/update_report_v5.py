"""§5-I 예실차 + §5-J CSM 무브먼트 — §5-H 사업비 다음에 삽입."""
from __future__ import annotations
import json
from pathlib import Path

R = Path("report")
report = R / "종합보고서_FY2025.html"
html = report.read_text(encoding="utf-8")

matrix = json.loads((R / "line_values_matrix.json").read_text(encoding="utf-8"))
acturial = json.loads((R / "actuarial_by_year.json").read_text(encoding="utf-8"))
opex = json.loads((R / "operating_expense_results.json").read_text(encoding="utf-8"))
csm_mov = json.loads((R / "csm_movement.json").read_text(encoding="utf-8"))

PEER_CIKS = ["00112332", "00126256", "00113058", "00117267",
             "00139214", "00164973", "00159102", "00135917"]
PEER_NAMES = {"00112332":"미래에셋","00126256":"삼성생명","00113058":"한화생명","00117267":"동양생명",
              "00139214":"삼성화재","00164973":"현대해상","00159102":"DB손보","00135917":"한화손보"}

# ─── §5-I 예실차 ───
i_block = """<h2>5-I. 예실차 (Expected vs Actual Claims) — 보험금 가정 정확도</h2>
<p>실제 발생한 보험금이 예상 대비 어떻게 차이나는지. 두 방법:</p>

<h3>방법 A · ≤1년 만기 예상보험금 vs 당기 실제 발생사고비용</h3>
<p>만기 1년 이내 예상금액과 당기 실제값 비교. 비율 100% 초과 → 실제 &gt; 예상 (위험):</p>
<div class="table-wrap">
<table>
<thead><tr><th>회사</th><th>≤1년 예상보험금</th><th>당기 실제발생사고</th><th>예실차 (절대)</th><th>실제/예상</th><th>시그널</th></tr></thead>
<tbody>
"""
for cik in PEER_CIKS:
    exp_1y = acturial["예상보험금"].get(cik, {}).get("≤1년")
    actual = matrix.get("발생사고비용", {}).get(cik)
    diff = ratio = None
    if exp_1y and actual and abs(exp_1y) > 1e8:
        diff = actual - exp_1y; ratio = actual / exp_1y * 100
    def f(v): return f"{v/1e8:,.0f}억" if v else "—"
    cls = "self" if cik == "00112332" else ""

    ratio_cls = ""; signal = "보고 부분"
    if ratio is not None:
        if ratio > 110: ratio_cls = " fail-cell"; signal = "⚠ 실제 &gt; 예상 위험"
        elif ratio > 100: ratio_cls = " warn-cell"; signal = "실제 ≳ 예상"
        elif ratio > 80: ratio_cls = " pass-cell"; signal = "✓ 실제 ≈ 예상"
        else: ratio_cls = " pass-cell"; signal = "✓ 실제 &lt;&lt; 예상 (보수적)"
    ratio_s = f"{ratio:.1f}%" if ratio else "—"
    i_block += f'<tr class="{cls}"><td class="company">{PEER_NAMES[cik]}</td>'
    i_block += f'<td class="num">{f(exp_1y)}</td><td class="num">{f(actual)}</td>'
    i_block += f'<td class="num">{f(diff)}</td><td class="num{ratio_cls}">{ratio_s}</td><td>{signal}</td></tr>'
i_block += """</tbody></table></div>

<h3>방법 B · 경험조정 (IFRS17 §103) ÷ 보험수익</h3>
<p>경험조정 = 실제 − 예상. 양수면 실제가 예상 초과(보험금 더 발생). 보험수익 대비 비율로 정규화:</p>
<div class="table-wrap">
<table>
<thead><tr><th>회사</th><th>경험조정</th><th>보험수익</th><th>조정/수익</th><th>의미</th></tr></thead>
<tbody>
"""
for cik in PEER_CIKS:
    exp_adj = matrix.get("경험조정", {}).get(cik)
    revenue = opex.get(cik, {}).get("보험수익")
    ratio = None
    if exp_adj is not None and revenue and abs(revenue) > 1e8:
        ratio = exp_adj / revenue * 100
    cls = "self" if cik == "00112332" else ""
    def f(v):
        if v is None: return "—"
        return f"{v/1e8:+,.0f}억"
    ratio_cls = ""; meaning = "—"
    if exp_adj is not None and ratio is not None:
        if exp_adj > 0:
            meaning = "실제 &gt; 예상 (보험금 더 발생)"
            if ratio > 5: ratio_cls = " warn-cell"
            elif ratio > 0: ratio_cls = ""
        elif exp_adj < 0:
            meaning = "✓ 실제 &lt; 예상 (보험금 덜 발생, 유리)"
            ratio_cls = " pass-cell"
    ratio_s = f"{ratio:+.2f}%" if ratio is not None else "—"
    i_block += f'<tr class="{cls}"><td class="company">{PEER_NAMES[cik]}</td>'
    i_block += f'<td class="num">{f(exp_adj)}</td><td class="num">{f(revenue)}</td>'
    i_block += f'<td class="num{ratio_cls}">{ratio_s}</td><td>{meaning}</td></tr>'
i_block += """</tbody></table></div>

<p><b>핵심 시그널</b>:</p>
<ul>
<li><b>방법 A</b>: 삼성화재 239%, 동양 165%, 한화생명 144% — 실제 발생사고가 단년 예상의 1.4~2.4배 (만기 분해 정확도 점검 필요). DB손보 55%, 현대해상 85%는 보수적.</li>
<li><b>방법 B</b>: <b>DB손보만 −0.67%</b> (예상 적중) ✓, 나머지 7개사 모두 +1.4~7.4% (소폭 실제 초과). 한화생명 +7.37%로 가장 큰 양의 차이.</li>
<li><b>자사 미래에셋 (방법 B)</b>: +2.49% — 동업사 평균(+3.0%) 보다 양호. <b>예실차가 작아 가정 정확도 양호</b>.</li>
</ul>

<div class="conclusion">
<h4>📌 자사 예실차 시사점</h4>
<ul>
<li><b>경험조정 +269억 / 보험수익 10,804억 = +2.49%</b> — 8개사 중 3번째로 작음 (DB −0.67% &lt; 삼성화재 +1.43% &lt; 미래에셋 +2.49%)</li>
<li>예상 보험금 가정이 동업사 대비 정확한 편. 단, §5-F-(연도별) 결과처럼 1년 단위 분해는 미공시 → 정밀 분석 위해 만기 분해 보고 필요</li>
<li><b>DB손보 −0.67% 사례</b> 참고 가치 — 유일하게 예상 보험금이 실제 초과 (회사가 보수적으로 가정)</li>
</ul>
</div>
"""

# ─── §5-J CSM 무브먼트 ───
j_block = """<h2>5-J. CSM 변동 무브먼트 — 8개사 (FY2025 별도, 억원)</h2>
<p>CSM(보험계약마진) 기시 → 변동 → 기말 흐름. ComponentsAxis=CSM 분해 합산. <b>검증식 오차 = (기시 + Σ변동) − 기말</b>:</p>
<div class="table-wrap">
<table>
<thead><tr><th>회사</th><th>기시 CSM</th><th>신계약</th><th>CSM 조정</th><th>미조정</th><th>경험조정</th><th>과거서비스</th><th>금융손익</th><th>CSM 상각</th><th>변동 합</th><th>기말 (실측)</th><th>오차</th></tr></thead>
<tbody>
"""
COLS_DISPLAY = ["기시 CSM", "신계약 인식", "CSM 조정 추정변동", "CSM 미조정 추정변동", "경험조정",
                "과거서비스 변동", "보험금융손익", "CSM 상각(보험수익)", "변동 합", "기말 CSM (실측)", "오차"]

for cik in PEER_CIKS:
    r = csm_mov[cik]
    cls = "self" if cik == "00112332" else ""
    def f(v):
        if v is None: return "—"
        return f"{v/1e8:+,.0f}"
    j_block += f'<tr class="{cls}"><td class="company">{PEER_NAMES[cik]}</td>'
    for c in COLS_DISPLAY:
        v = r.get(c)
        # 오차에 따라 색상
        if c == "오차" and v is not None:
            err_pct = abs(v) / abs(r.get("기말 CSM (실측)", 1)) * 100 if r.get("기말 CSM (실측)") else 0
            if err_pct > 20: cell_cls = " fail-cell"
            elif err_pct > 5: cell_cls = " warn-cell"
            else: cell_cls = " pass-cell"
            j_block += f'<td class="num{cell_cls}">{f(v)}</td>'
        else:
            j_block += f'<td class="num">{f(v)}</td>'
    j_block += '</tr>'
j_block += """</tbody></table></div>

<p><b>주요 관찰</b>:</p>
<ul>
<li><b>신계약 CSM 인식 (FY2025)</b>: 삼성화재 +86,640억 (압도) &gt; 한화생명 +41,325 &gt; 현대 +34,579 &gt; DB +28,820 &gt; <b>미래에셋 +10,513</b> &gt; 한화손보 +10,178 &gt; 동양 +5,251 &gt; 삼성생명 +1억</li>
<li><b>CSM 조정 추정변동</b>: 한화생명 −40,644 (가정 하향), 삼성화재 −51,216 (가정 큰 하향), 미래에셋 −3,984 (소폭 하향)</li>
<li><b>경험조정·CSM 상각 등 일부 라인은 element 매핑 한계로 회사별 누락</b> — 동양생명만 오차 +95억으로 거의 정확, 다른 회사 오차 큼 (한계 footer 참조)</li>
</ul>

<div class="conclusion warning">
<h4>⚠️ CSM 무브먼트 한계</h4>
<ul>
<li>회사마다 element_id 다양성 + entity 확장 element 사용으로 일부 변동 라인 누락. 오차 큰 회사는 누락 라인 추정 필요.</li>
<li>특히 <b>CSM 상각 (보험수익 인식)</b> element 가 회사마다 변형 다양 — 표준 <code>InsuranceRevenueContractualServiceMarginRecognisedInProfitOrLossBecauseOfTransferOfServices</code> 외에 dart_ / entity_ 변형 존재</li>
<li>정밀 분석 위해선 회사별 사업보고서 원본 XBRL의 pre.xml 매핑 dict 필요 (미래에셋 사례처럼)</li>
<li>그럼에도 신계약 인식·CSM 조정 추정변동 같은 핵심 변동은 모든 회사 보고 → 8개사 비교 의미 있음</li>
</ul>
</div>

<h3>자사 미래에셋 CSM 흐름 요약</h3>
<table>
<tr><td class="label">기시 CSM (2024-12-31)</td><td class="num">+20,782억</td></tr>
<tr><td class="label">+ 신계약 인식</td><td class="num">+10,513억</td></tr>
<tr><td class="label">+ CSM 조정 추정변동 (net)</td><td class="num">+1,415억</td></tr>
<tr><td class="label">+ 경험조정</td><td class="num">+288억</td></tr>
<tr><td class="label">+ 보험금융손익</td><td class="num">+1,213억</td></tr>
<tr><td class="label">+ CSM 상각·기타 (역산)</td><td class="num">−13,627억</td></tr>
<tr style="background:#fff7e0;font-weight:600"><td class="label">기말 CSM (2025-12-31)</td><td class="num">+20,584억 (변동 −198, −1.0%)</td></tr>
</table>
<p>자사 CSM은 신계약 +1.05조와 상각 −1.36조가 거의 상쇄, 결과적으로 잔액 안정. 다만 절대 규모 2.06조는 동업사 중 가장 작음 — 신계약 영업 확대 여부 검토 가치.</p>
"""

# §6 IFRS17 가정 앞에 §5-I + §5-J 삽입
html = html.replace('<h2>6. IFRS17 회계가정 적용 사항</h2>',
                     i_block + j_block + '<h2>6. IFRS17 회계가정 적용 사항</h2>')

report.write_text(html, encoding="utf-8")
print(f"updated {report} ({len(html):,} bytes)")
