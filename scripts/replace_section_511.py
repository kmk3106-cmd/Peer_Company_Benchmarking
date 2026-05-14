"""§5.11 잘못된 가정 변동 섹션 → 정확 데이터로 교체.

기존: 8개사 가정 변동 (유추 매핑된 element)
신규: 미래에셋 entity00112332 정확 element만 사용 (`계리적가정에 의한 보험부채 변동내역`)
"""
from __future__ import annotations
import re
from pathlib import Path

report = Path("report/종합보고서_FY2025.html")
html = report.read_text(encoding="utf-8")

# 정확 추출 결과 (단위: 억원)
EXACT_DATA = [
    ("신계약에 기인한 미래서비스의 변동", -6015, 700, 5399, 84),
    ("신계약 외 미래서비스 변동 (합계)", -3294, -202, 3496, 0),
    ("── 가정변경 효과 — 해지율 가정변경", 2548, 0, -2548, 0),
    ("── 가정변경 효과 — 위험율 가정변경", 2317, 0, -2317, 0),
    ("── 가정변경 효과 — 예정율 가정변경", 450, 0, -450, 0),
    ("── 가정변경 효과 — 기타 가정변경", 2910, 0, -2910, 0),
    ("── 보유물량·투자요소 차이", -3294, -202, 3496, 0),
    ("── 손실요소에 의한 변동", 0, 0, 583, 583),
]

new_511 = """<h2 id="sec-5-11-계리적가정에-의한-보험부채-변동내역-미래에셋-정확-search">5.11 계리적가정에 의한 보험부채 변동내역 (미래에셋, 정확 search)</h2>

<div class="conclusion warning">
<h4>⚠️ 정정 안내</h4>
<p>이전 버전(2026-05-14 이전)은 <code>entity_ChangeEffectOfDiscountRateAndFinancialAssumption</code> 같은 유사 element를 유추 매핑해 잘못된 값을 보고했음. 사용자 피드백 후 <b>미래에셋 사업보고서 원본 XBRL의 정확 element만 사용</b>으로 정정:</p>
<ul>
<li>원천 element: <code>entity00112332_ChangesInInsuranceLiabilitiesBasedOnActuarialAssumptionsTable</code> (역할 <code>DI817100</code> + <code>DI817105</code>)</li>
<li>자식 line items: <code>presentation tree.PARENT_ELEMENT_ID</code> 로 walk</li>
<li>축: <code>InsuranceContractsByComponentsAxis</code> = BEL / RA / CSM (CSM은 standard + transition 3변형)</li>
<li>기준: 별도(SeparateMember) + 발행(InsuranceContractsIssuedMember) + duration 2025</li>
</ul>
</div>

<div class="table-wrap">
<table>
<thead><tr><th>변동 항목</th><th>BEL</th><th>RA</th><th>CSM</th><th>합계</th></tr></thead>
<tbody>
"""

for label, bel, ra, csm, total in EXACT_DATA:
    is_subtotal = "합계" in label or label.startswith("신계약")
    tr_attr = ' style="background:#f0f5fb;font-weight:600"' if is_subtotal else ""
    def f(v):
        if v == 0: return "0"
        return f"{v:+,}"
    new_511 += f'<tr{tr_attr}><td class="label">{label}</td>'
    new_511 += f'<td class="num">{f(bel)}</td><td class="num">{f(ra)}</td><td class="num">{f(csm)}</td>'
    new_511 += f'<td class="num"><b>{f(total)}</b></td></tr>'

new_511 += """</tbody></table></div>

<p><b>핵심 관찰 (IFRS17 §103 표준 회계처리)</b>:</p>
<ul>
<li><b>가정 변경 효과는 BEL ↑ ↔ CSM ↓ 대칭</b> — 합계 0. 즉 가정 변동이 CSM을 통해 모두 흡수되어 당기 P&L 영향 0:
    <ul>
    <li>해지율 가정변경: BEL +2,548 / CSM −2,548</li>
    <li>위험율 가정변경: BEL +2,317 / CSM −2,317</li>
    <li>예정율 가정변경: BEL +450 / CSM −450</li>
    <li>기타 가정변경: BEL +2,910 / CSM −2,910 (최대)</li>
    <li><b>가정변경 효과 BEL 합계 +8,225 / CSM 합계 −8,225</b> — 부채는 BEL 늘었으나 CSM이 그만큼 줄어 net 0</li>
    </ul>
</li>
<li><b>신계약 기인 미래서비스 변동</b>: BEL −6,015 / RA +700 / CSM +5,399 → 합계 +84억 (소폭 부채 증가)</li>
<li><b>손실요소에 의한 변동</b>: CSM +583억 → 손실부담계약 환입 (유리)</li>
<li><b>보유물량·투자요소 차이</b>: BEL −3,294 / RA −202 / CSM +3,496 (가정 변경과 별개로 실제 contract volume 차이 영향)</li>
</ul>

<div class="conclusion">
<h4>📌 자사 계리적 가정 종합 시사점</h4>
<ul>
<li><b>가정 변경 효과 BEL 8,225억 (총 +)</b> — 미래에셋이 FY2025 중 가정을 보수적으로 갱신 (해지율·위험율·예정율 모두 부채 증가 방향)</li>
<li><b>그러나 CSM이 동일 금액 흡수</b> → 당기 PL 영향 0. IFRS17 §103 회계처리 표준 정합 ✓</li>
<li><b>가정 변경 비중</b>: 기타 가정변경 35.4% &gt; 해지율 31.0% &gt; 위험율 28.2% &gt; 예정율 5.5% — 사업비 가정 외 미분류 항목 비중이 가장 큼 (구체 항목 식별 필요)</li>
<li><b>한계</b>: 다른 7개사도 비슷한 표 있는지 별도 search 필요. 미래에셋만 entity 확장 element로 별도 공시 (다른 회사는 §5.7 변동표의 추정변동 element로만 통합 보고)</li>
</ul>
</div>

<p><b>원천 element 출처</b> (감사 추적용):</p>
<ul style="font-size:9pt;color:#666;">
<li><code>entity00112332_ChangesInFutureServicesDueToNewContractsOfChangesInInsuranceLiabilitiesBasedOnActuarialAssumptionsTableOfItems</code></li>
<li><code>entity00112332_ChangesInFutureServicesAttributableToFactorsOtherThanNewContractsOfChangesInInsuranceLiabilitiesBasedOnActuarialAssumptionsTableOfItems</code></li>
<li><code>entity00112332_ChangeInCancellationRateAssumptionOf...</code> (해지율)</li>
<li><code>entity00112332_ChangeInRiskRateAssumptionOf...</code> (위험율)</li>
<li><code>entity00112332_ChangeInProjectRatioAssumptionOf...</code> (예정율)</li>
<li><code>entity00112332_OtherAssumptionChangesOf...</code> (기타)</li>
<li><code>entity00112332_FluctuationsDueToVolumeDifferencesAndDifferencesInInvestmentFactors...</code></li>
<li><code>entity00112332_FluctuationsDueToLossFactorsOfChangesInFutureServices...</code></li>
</ul>
"""

# 기존 §5.11 영역 교체 (h2 5.11 부터 다음 h2 5.12 직전까지)
old_511_pattern = re.compile(
    r'<h2[^>]*>5\.11.*?(?=<h2[^>]*>5\.12)', re.DOTALL
)
html = old_511_pattern.sub(new_511, html, count=1)

report.write_text(html, encoding="utf-8")
print(f"updated {report} ({len(html):,} bytes)")
