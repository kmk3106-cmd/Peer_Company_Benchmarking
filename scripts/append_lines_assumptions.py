"""기존 보고서에 §5-G(17 라인 실수치) + §6-A/B/C(IFRS17 가정) 섹션 append."""
from __future__ import annotations
import json
from pathlib import Path

R = Path("report")
report = R / "종합보고서_FY2025.html"
html = report.read_text(encoding="utf-8")

# 17 라인 매트릭스 load
matrix = json.loads((R / "line_values_matrix.json").read_text(encoding="utf-8"))

peer_ciks = ["00112332", "00126256", "00113058", "00117267",
             "00139214", "00164973", "00159102", "00135917"]
peer_names = {"00112332":"미래에셋","00126256":"삼성생명","00113058":"한화생명","00117267":"동양생명",
              "00139214":"삼성화재","00164973":"현대해상","00159102":"DB손보","00135917":"한화손보"}

LINE_ORDER = ["보험수익","신계약인식","CSM조정추정변동","CSM미조정추정변동","위험조정변동","경험조정",
              "과거서비스변동","손실부담계약손실","발생사고비용","수취보험료","지급보험금","보험취득CF지급",
              "보험취득CF상각","투자요소","금융손익_PL","금융손익_OCI","기타증감"]

# §5-G HTML
section_g = """
<h2>5-G. 변동표 실수치 17 라인 × 8개사 횡단비교 (FY2025 별도·발행, 단위 억원)</h2>
<p>자동 PASS 17 라인의 실제 변동분 합계. 음수 = 부채 감소 (revenue·지급), 양수 = 부채 증가:</p>
<div class="table-wrap">
<table>
<thead><tr><th>라인</th>"""
for cik in peer_ciks:
    cls = "self" if cik == "00112332" else ""
    section_g += f'<th class="{cls}">{peer_names[cik]}</th>'
section_g += '</tr></thead><tbody>'

for line in LINE_ORDER:
    row = matrix.get(line, {})
    section_g += f'<tr><td class="label">{line}</td>'
    for cik in peer_ciks:
        v = row.get(cik)
        cls = " self" if cik == "00112332" else ""
        if v is None or abs(v) < 1e8:
            section_g += f'<td class="num{cls}">—</td>'
        else:
            val_str = f"{v/1e8:+,.0f}"
            section_g += f'<td class="num{cls}">{val_str}</td>'
    section_g += '</tr>'
section_g += '</tbody></table></div>'
section_g += """
<p><b>주요 관찰</b>:</p>
<ul>
<li><b>수취보험료 규모</b>: 삼성생명 418천억 (압도) &gt; 삼성화재 358천억 &gt; 한화생명 167천억 &gt; 미래에셋 69천억 &gt; DB 65천억 &gt; 현대 61천억</li>
<li><b>지급보험금 비율</b>: 모두 수취보험료의 약 60~110% 수준. 자사 124.4% (지급 86천억 / 수취 69천억) — 상대적 지급률 높음</li>
<li><b>보험취득CF 지급 규모</b>: 미래에셋 181천억은 BS 27조 대비 67% — 매우 큼 (전체 8개사 중 자산 대비 최대 비중)</li>
<li><b>금융손익 PL</b>: 삼성생명 +74천억 (이익), 미래에셋 -22천억 (손실), 손보 -4~13천억</li>
<li><b>위험조정 변동</b>: 미래에셋 -191억 (절대값 최소) — RA 변동 가장 작음. 한화생명·삼성생명은 천억 단위</li>
</ul>"""

# §6 IFRS17 가정
section_6 = """
<h2>6. IFRS17 회계가정 적용 사항</h2>

<h3>6-A. 측정모형 분포 (단위 조원)</h3>
<p>IFRS17 측정모형: <b>PAA</b>(보험료배분, 단기) · <b>GMM</b>(일반모형, 보장성) · <b>VFA</b>(변동수수료, 변액·직접참여):</p>
<div class="table-wrap">
<table>
<thead><tr><th>회사</th><th>구분</th><th>PAA</th><th>Non-PAA</th><th>GMM</th><th>VFA</th><th>적용 모형</th></tr></thead>
<tbody>
<tr class="self"><td class="company">미래에셋생명</td><td>생보</td><td class="num">—</td><td class="num">108.0조</td><td class="num">—</td><td class="num">108.0조</td><td>생보 — VFA 위주</td></tr>
<tr><td class="company">삼성생명</td><td>생보</td><td class="num">—</td><td class="num">200.9조</td><td class="num">—</td><td class="num">200.9조</td><td>생보 — VFA</td></tr>
<tr><td class="company">한화생명</td><td>생보</td><td class="num">0.01조</td><td class="num">96.9조</td><td class="num">96.9조</td><td class="num">96.9조</td><td>생보 — GMM+VFA</td></tr>
<tr><td class="company">동양생명</td><td>생보</td><td class="num">28.2조</td><td class="num">28.2조</td><td class="num">28.2조</td><td class="num">28.2조</td><td>생보 — GMM+VFA</td></tr>
<tr><td class="company">삼성화재</td><td>손보</td><td class="num">7.6조</td><td class="num">82.2조</td><td class="num">—</td><td class="num">—</td><td>손보 — PAA + Non-PAA</td></tr>
<tr><td class="company">현대해상</td><td>손보</td><td class="num">3.5조</td><td class="num">31.4조</td><td class="num">—</td><td class="num">—</td><td>손보 — PAA + Non-PAA</td></tr>
<tr><td class="company">DB손해보험</td><td>손보</td><td class="num">6.1조</td><td class="num">52.5조</td><td class="num">—</td><td class="num">—</td><td>손보 — PAA + Non-PAA</td></tr>
<tr><td class="company">한화손해보험</td><td>손보</td><td class="num">1.7조</td><td class="num">13.6조</td><td class="num">—</td><td class="num">—</td><td>손보 — PAA + Non-PAA</td></tr>
</tbody></table>
</div>
<p><b>패턴</b>:</p>
<ul>
<li><b>손보 4개사</b>: PAA + Non-PAA 명확 — PAA(자동차·일반 단기) 비중 9~14%, Non-PAA(장기) 86~91%</li>
<li><b>생보 4개사</b>: 거의 모두 Non-PAA. 한화·동양은 GMM+VFA 표준 axis 사용, 미래에셋·삼성생명은 VFA 위주 entity 멤버</li>
<li><b>자사 시사</b>: 미래에셋 VFA 위주 — 변액·직접참여계약 비중 큼. 기초항목 공정가치 변동이 CSM에 직접 영향</li>
</ul>

<h3>6-B. CSM Transition Approach 적용 비중</h3>
<p>IFRS17 첫 적용시 기존 보험계약의 CSM 산정 방법 — 회계정책 선택의 핵심:</p>
<div class="table-wrap">
<table>
<thead><tr><th>회사</th><th>Modified Retrospective<br>(수정소급)</th><th>Fair Value<br>(공정가치)</th><th>NotRelated<br>(Full Retro + 신계약)</th><th>적용 여부</th></tr></thead>
<tbody>
<tr class="self"><td class="company">미래에셋생명</td><td class="num">17.3%</td><td class="num warn-cell">41.2%</td><td class="num">41.6%</td><td>전환계약 3분해 ✓</td></tr>
<tr><td class="company">삼성생명</td><td class="num">8.5%</td><td class="num">32.5%</td><td class="num pass-cell">59.1%</td><td>전환계약 3분해 ✓</td></tr>
<tr><td class="company">한화생명</td><td class="num">—</td><td class="num">—</td><td class="num">—</td><td class="warn-cell">standard 단일 보고 (transition 미분해)</td></tr>
<tr><td class="company">동양생명</td><td class="num">30.7%</td><td class="num">13.5%</td><td class="num">55.8%</td><td>전환계약 3분해 ✓</td></tr>
<tr><td class="company">삼성화재</td><td class="num">—</td><td class="num">—</td><td class="num">—</td><td class="warn-cell">standard 단일 보고</td></tr>
<tr><td class="company">현대해상</td><td class="num">—</td><td class="num">—</td><td class="num">—</td><td class="warn-cell">standard 단일 보고</td></tr>
<tr><td class="company">DB손해보험</td><td class="num">22.2%</td><td class="num">32.8%</td><td class="num">44.9%</td><td>전환계약 3분해 ✓</td></tr>
<tr><td class="company">한화손해보험</td><td class="num">24.5%</td><td class="num">28.7%</td><td class="num">46.7%</td><td>전환계약 3분해 ✓</td></tr>
</tbody></table>
</div>
<p><b>패턴</b>:</p>
<ul>
<li><b>Transition 분해 보고 (5개사)</b>: 미래에셋·삼성생명·동양·DB·한화손보 — 전환시점 계약을 3가지 방법으로 분해 공시</li>
<li><b>standard CSM 단일 보고 (3개사)</b>: 한화생명·삼성화재·현대해상 — transition 분해 미공시. 회계정책 단순화 또는 신계약 위주 사업</li>
<li><b>Fair Value 비중 ranking</b>: 미래에셋 41.2% &gt; DB 32.8% &gt; 삼성생명 32.5% &gt; 한화손보 28.7% &gt; 동양 13.5%</li>
<li><b>자사 시사</b>: <b>미래에셋 FairValue 41.2% — 동업사 중 최대</b>. 전환시점 다수 계약을 공정가치법으로 인식 → 시장가격 가정 의존도 큼. 시장 변동시 CSM 변동성 노출</li>
</ul>

<h3>6-C. 보험금융손익 PL vs OCI 회계정책</h3>
<p>IFRS17 §88 회계정책 선택: 보험금융손익을 <b>PL 일괄</b> 또는 <b>PL+OCI 분리</b>(자산-부채 매칭 위해):</p>
<div class="table-wrap">
<table>
<thead><tr><th>회사</th><th>PL 비중</th><th>OCI 활용</th><th>회계정책</th><th>시사</th></tr></thead>
<tbody>
<tr class="self"><td class="company">미래에셋생명</td><td class="num warn-cell">98.6%</td><td class="num">1.4%</td><td>PL only</td><td>변동성 PL 직격 — 보수·투명</td></tr>
<tr><td class="company">삼성생명</td><td class="num warn-cell">100.0%</td><td class="num">—</td><td>PL only</td><td>변동성 PL 직격</td></tr>
<tr><td class="company">한화생명</td><td class="num">—</td><td class="num">—</td><td>(매핑 한계)</td><td>—</td></tr>
<tr><td class="company">동양생명</td><td class="num">58.2%</td><td class="num">41.8%</td><td>PL+OCI 혼합</td><td>OCI 활용 — PL 완화</td></tr>
<tr><td class="company">삼성화재</td><td class="num">57.9%</td><td class="num">42.1%</td><td>PL+OCI 혼합</td><td>OCI 활용 — PL 완화</td></tr>
<tr><td class="company">현대해상</td><td class="num">—</td><td class="num">—</td><td>(매핑 한계)</td><td>—</td></tr>
<tr><td class="company">DB손해보험</td><td class="num">—</td><td class="num">—</td><td>(매핑 한계)</td><td>—</td></tr>
<tr><td class="company">한화손해보험</td><td class="num">39.4%</td><td class="num pass-cell">60.6%</td><td>OCI 위주</td><td>PL 안정성 우선</td></tr>
</tbody></table>
</div>
<p><b>패턴</b>:</p>
<ul>
<li><b>PL only (미래에셋·삼성생명)</b>: 보험금융손익 전액 PL 인식. 보수적·투명한 회계, PL 변동성 직격</li>
<li><b>PL+OCI 혼합 (동양·삼성화재 ~58%)</b>: 일부 OCI 우회로 PL 변동 완화</li>
<li><b>OCI 위주 (한화손보 OCI 60.6%)</b>: 보험금융손익 다수를 OCI 처리 — PL 안정성 우선</li>
<li><b>자사 시사</b>: <b>미래에셋 PL 98.6% — 가장 보수적 회계정책</b>. 시장이율·기초항목 변동시 PL 변동성 큰 노출. OCI 옵션 적용 검토 가치 있음 (단, 회계정책 변경은 일관성 영향 — 별도 검토)</li>
</ul>

<h3>6-D. IFRS17 가정 요약 — 자사 vs 동업사</h3>
<div class="conclusion warning">
<h4>⚠️ 미래에셋 IFRS17 가정 종합 시사점</h4>
<ul>
<li><b>① 측정모형</b>: VFA 위주 → 기초항목(주식·채권·자산연계) 공정가치 변동에 CSM 직접 노출</li>
<li><b>② Transition</b>: FairValue 41.2% (동업사 최대) → 전환시점 계약을 시장가격으로 인식. 시장 변동시 CSM 재산정 영향 큼</li>
<li><b>③ PL 회계정책</b>: PL only 98.6% → 시장이율 변동시 당기손익 변동성 직격 노출</li>
<li><b>종합</b>: 자사는 <b>시장가격·이율 가정에 가장 민감</b>한 회계정책 채택. 자산-부채 매칭(126%) 양호하나 변동성 흡수 capacity (OCI 등) 활용 여지 있음</li>
</ul>
</div>
"""

# 삽입 위치: <h2>6. 자사(미래에셋생명) 인사이트</h2> 앞에 §5-G + §6
insert_marker = '<h2>6. 자사(미래에셋생명) 인사이트</h2>'
new_marker = section_g + section_6 + '\n<h2>7. 자사(미래에셋생명) 인사이트</h2>'

new_html = html.replace(insert_marker, new_marker)
# § 7 "한계 및 다음 단계" → §8
new_html = new_html.replace('<h2>7. 분석 한계 및 다음 단계</h2>', '<h2>8. 분석 한계 및 다음 단계</h2>')

report.write_text(new_html, encoding="utf-8")
print(f"updated {report} ({len(new_html):,} bytes, +{len(new_html)-len(html):,} bytes)")
