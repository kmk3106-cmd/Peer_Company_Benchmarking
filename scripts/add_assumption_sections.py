"""§5.11 계리적 가정 변동내역 + §5.12 CSM 상각률 추가."""
from __future__ import annotations
import json
from pathlib import Path

R = Path("report")
report = R / "종합보고서_FY2025.html"
html = report.read_text(encoding="utf-8")

csm_am = json.loads((R / "csm_amortization.json").read_text(encoding="utf-8"))
assumptions = json.loads((R / "assumption_changes.json").read_text(encoding="utf-8"))

PEER_CIKS = ["00112332","00126256","00113058","00117267","00139214","00164973","00159102","00135917"]
PEER_NAMES = {"00112332":"미래에셋","00126256":"삼성생명","00113058":"한화생명","00117267":"동양생명",
              "00139214":"삼성화재","00164973":"현대해상","00159102":"DB손보","00135917":"한화손보"}

# ─── §5.11 계리적 가정 변동내역 ───
ASSUMPTION_ORDER = [
    "신계약 효과", "CSM 조정 추정변동", "CSM 미조정 추정변동",
    "위험조정 변동", "경험조정", "손실부담계약 손실(환입)",
    "할인률·금융가정 변경", "위험율 가정변경", "해지율 가정변경", "환율변동 효과",
]

a_block = """<h2>5.11 계리적 가정 변동에 따른 부채 변동내역</h2>
<p>IFRS17 §103 가정 변동 요소별 보험계약부채 영향. 양수 = 부채 증가 (불리), 음수 = 부채 감소 (유리). 단위 억원:</p>
<div class="table-wrap">
<table>
<thead><tr><th>가정 항목</th>"""
for cik in PEER_CIKS:
    cls = "self" if cik == "00112332" else ""
    a_block += f'<th class="{cls}">{PEER_NAMES[cik]}</th>'
a_block += '</tr></thead><tbody>'

for line in ASSUMPTION_ORDER:
    row = assumptions.get(line, {})
    a_block += f'<tr><td class="label">{line}</td>'
    for cik in PEER_CIKS:
        v = row.get(cik)
        cls = "num self" if cik == "00112332" else "num"
        if v is None or abs(v) < 1e7:
            a_block += f'<td class="{cls}">—</td>'
        else:
            a_block += f'<td class="{cls}">{v/1e8:+,.0f}</td>'
    a_block += '</tr>'
a_block += """</tbody></table></div>

<p><b>핵심 관찰</b>:</p>
<ul>
<li><b>신계약 효과 ranking</b>: 삼성화재 +57,967억 (압도) &gt; 현대해상 +23,309 &gt; 한화생명 +20,663 &gt; <b>미래에셋 미공시</b> (CSM 무브먼트 §5.10에서는 +10,513억 보고)</li>
<li><b>CSM 조정 추정변동 (가정 하향, 부채 증가)</b>: 삼성화재 −33,722 (큰 하향), 한화생명 −20,322, 현대 −7,190, 미래에셋 +583 (소폭 상향)</li>
<li><b>위험조정 변동</b>: 모두 음수 (RA 해소로 부채 감소). 자사 −191억 = 동업사 최저 절대값. 삼성생명 −6,911, 삼성화재 −1,648 등</li>
<li><b>경험조정</b>: DB손보만 음수(−1,023, 유리), 나머지 7사 양수 (불리 — 실제가 예상 초과). 자사 +269억으로 동업사 중 최소</li>
<li><b>할인률·금융가정 변경</b>: <b>미래에셋만 별도 분해 보고 +4,835억</b> (시장이율 변동으로 부채 증가). 다른 회사는 CSM 조정 추정변동에 통합 보고</li>
</ul>

<div class="conclusion">
<h4>📌 자사 가정 변동 시사점</h4>
<ul>
<li><b>할인률·금융가정 변경 +4,835억</b> — 시장이율 가정 변동시 부채 증가 큰 폭. VFA 위주 사업과 일관 (시장 민감도 큼)</li>
<li><b>RA 변동 절대값 −191억 = 동업사 최소</b> — 위험조정 산정이 가장 안정적이거나 RA 규모 자체가 작아 변동 적음</li>
<li><b>경험조정 +269억 = 동업사 중 3번째로 작음</b> — 보험금 예측 정확도 양호</li>
</ul>
</div>
"""

# ─── §5.12 CSM 상각률 ───
b_block = """<h2>5.12 보험계약마진(CSM) 상각률</h2>
<p>당기 CSM 상각액 ÷ 평균 CSM × 100%. 정상 장기 보험사 8~15% 범위. 단위 억원·%:</p>
<div class="table-wrap">
<table>
<thead><tr><th>회사</th><th>기시 CSM</th><th>기말 CSM</th><th>평균 CSM</th><th>당기 상각액</th><th>상각률</th><th>비고</th></tr></thead>
<tbody>
"""

def f(v): return f"{v/1e8:+,.0f}억" if v else "—"
for cik in PEER_CIKS:
    r = csm_am[cik]
    cls = "self" if cik == "00112332" else ""
    rate = r.get("rate")
    rate_cls = ""; note = ""
    if rate is not None:
        if rate < 5:
            rate_cls = " warn-cell"; note = "비정상 낮음"
        elif rate < 8:
            rate_cls = ""; note = "장기 위주"
        elif rate < 15:
            rate_cls = " pass-cell"; note = "정상 범위 (장기)"
        elif rate < 30:
            rate_cls = " warn-cell"; note = "중기 또는 element 한계"
        else:
            rate_cls = " fail-cell"; note = "element 중복 매핑 한계 ⚠"
    rate_s = f"<b>{rate:.1f}%</b>" if rate else "—"
    b_block += f'<tr class="{cls}"><td class="company">{PEER_NAMES[cik]}</td>'
    b_block += f'<td class="num">{f(r["beg"])}</td><td class="num">{f(r["end"])}</td><td class="num">{f(r["avg"])}</td>'
    b_block += f'<td class="num">{f(r["amort"])}</td><td class="num{rate_cls}">{rate_s}</td><td>{note}</td></tr>'

b_block += """</tbody></table></div>

<p><b>상각률 ranking (8개사)</b>:</p>
<ol>
<li><b>한화생명 8.5%</b> — 가장 낮음 (초장기 보험 비중 큼, §5.4 CSM 만기 30년+ 45.6% 일관)</li>
<li>동양생명 9.5%</li>
<li>한화손보 10.7%</li>
<li>현대해상 11.0%</li>
<li>삼성화재 11.1%</li>
<li>삼성생명 11.8%</li>
<li><b>DB손보 11.9%</b> — 가장 높음 (단기 비중 큼)</li>
<li><b>미래에셋 102.0%</b> ⚠ — element 매핑 한계로 over-count (실제는 65~70% 추정)</li>
</ol>

<div class="conclusion warning">
<h4>⚠️ 자사 CSM 상각률 분석 한계</h4>
<ul>
<li><b>미래에셋 102%</b>는 비현실적 — <code>InsuranceRevenueContractualServiceMargin...</code> + <code>IncreaseDecreaseThroughRecognitionOfContractualServiceMargin...</code> 두 element 합산시 같은 fact 중복 포함</li>
<li>역산 추정: §5.10 CSM 무브먼트에서 미래에셋 기말잔액 검증식 차이 −13,627억 = 추정 상각액. 평균 CSM 20,683 대비 <b>약 65.9%</b>로 비정상 높음 (의심)</li>
<li>한 가지 가능성: 미래에셋 CSM 잔액 자체가 transition 멤버를 포함하지 않은 standard CSM만 (2.06조) 이라 평균 작고, 상각이 transition 포함된 큰 값이라 비율 부풀려짐</li>
<li>정밀 산출 위해선 회사별 pre.xml의 정확한 CSM 상각 element 매핑 필요</li>
</ul>
</div>

<h3>5.12-(보조) CSM 상각률 의미 — 계리적 해석</h3>
<ul>
<li><b>상각률 8~12% (정상 장기)</b>: 보험계약 잔존기간 8~12년 평균. 한화생명·동양 = 장기 보험 위주, DB손보 = 상대 단기</li>
<li><b>상각률 자체는 단기 효율 지표가 아님</b>: 상각률 낮음 = 장기 사업 (CSM 인식 늦음, 이익 발생 늦음 but 안정적). 높음 = 단기 사업 (CSM 빠르게 소진, 신계약 의존)</li>
<li><b>신계약 CSM (§5.10) vs CSM 상각률 결합 해석</b>:
    <ul>
    <li>삼성화재: 신계약 +86,640 & 상각률 11.1% → 단기 사업·신계약 매우 적극</li>
    <li>한화생명: 신계약 +41,325 & 상각률 8.5% → 장기·신계약 큼 (균형)</li>
    <li>미래에셋: 신계약 +10,513 (생보 중 최소) — CSM 절대 규모도 작아 영업 확대 여지</li>
    </ul>
</li>
</ul>
"""

# §6 IFRS17 가정 앞에 §5.11 + §5.12 삽입
html = html.replace('<h2 id="sec-6-IFRS17-회계가정-적용">6. IFRS17 회계가정 적용</h2>',
                     a_block + b_block + '<h2 id="sec-6-IFRS17-회계가정-적용">6. IFRS17 회계가정 적용</h2>')

# TOC도 갱신해야 함 — tidy_toc 다시 실행 필요
report.write_text(html, encoding="utf-8")
print(f"updated {report} ({len(html):,} bytes)")
