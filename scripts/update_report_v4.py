"""§5-G 잔액 추가 + §5-F-Year 연도별 + §5-H 사업비 — 안전한 삽입."""
from __future__ import annotations
import json
from pathlib import Path

R = Path("report")
report = R / "종합보고서_FY2025.html"
html = report.read_text(encoding="utf-8")

line_matrix = json.loads((R / "line_values_matrix.json").read_text(encoding="utf-8"))
acturial_year = json.loads((R / "actuarial_by_year.json").read_text(encoding="utf-8"))
opex = json.loads((R / "operating_expense_results.json").read_text(encoding="utf-8"))

PEER_CIKS = ["00112332", "00126256", "00113058", "00117267",
             "00139214", "00164973", "00159102", "00135917"]
PEER_NAMES = {"00112332":"미래에셋","00126256":"삼성생명","00113058":"한화생명","00117267":"동양생명",
              "00139214":"삼성화재","00164973":"현대해상","00159102":"DB손보","00135917":"한화손보"}
SECTORS = {"00112332":"생보","00126256":"생보","00113058":"생보","00117267":"생보",
           "00139214":"손보","00164973":"손보","00159102":"손보","00135917":"손보"}

# ─── 1) §5-G 기존 17 라인 + 기시/기말 (새 매트릭스) ───
LINE_ORDER = list(line_matrix.keys())  # 이미 기초 첫 행, 기말 끝 행으로 정렬됨

new_g_table = '<div class="table-wrap"><table><thead><tr><th>라인</th>'
for cik in PEER_CIKS:
    cls = "self" if cik == "00112332" else ""
    new_g_table += f'<th class="{cls}">{PEER_NAMES[cik]}</th>'
new_g_table += '</tr></thead><tbody>'

for line in LINE_ORDER:
    row = line_matrix[line]
    is_balance = "잔액" in line
    tr_attr = ' style="background:#fff7e0;font-weight:600"' if is_balance else ""
    new_g_table += f'<tr{tr_attr}><td class="label">{line}</td>'
    for cik in PEER_CIKS:
        v = row.get(cik)
        cls = "num self" if cik == "00112332" else "num"
        if v is None or abs(v) < 1e8:
            new_g_table += f'<td class="{cls}">—</td>'
        else:
            new_g_table += f'<td class="{cls}">{v/1e8:+,.0f}</td>'
    new_g_table += '</tr>'
new_g_table += '</tbody></table></div>'

# 기존 §5-G 표만 교체 (제목 + ul은 유지하되 내용 보강)
new_g_block = f"""<h2>5-G. 변동표 + 기시/기말 잔액 × 8개사 횡단비교 (FY2025 별도·발행, 단위 억원)</h2>
<p>17 변동 라인 + 기시(2024-12-31)·기말(2025-12-31) 잔액. 잔액 행은 노란색 강조:</p>
{new_g_table}
<p><b>잔액 변동 핵심</b>:</p>
<ul>
<li><b>자사 미래에셋</b>: 262,484 → 269,967 (<b>+7,483억, +2.9%</b>) — 부채 소폭 증가</li>
<li>삼성생명: 2,021,563 → 2,008,463 (−13,100억, −0.6%) — 안정</li>
<li>한화생명: 971,522 → 969,358 (−2,164억, −0.2%) — 거의 보합</li>
<li>동양생명: 282,215 → 281,451 (−764억, −0.3%)</li>
<li>삼성화재: 516,095 → 487,348 (<b>−28,747억, −5.6%</b>) — 부채 감소 최대</li>
<li>현대해상: 348,019 → 348,529 (+510억, +0.1%)</li>
<li>DB손보: 319,373 → 315,801 (−3,572억, −1.1%)</li>
<li>한화손보: 151,976 → 153,485 (+1,509억, +1.0%) — 소폭 증가</li>
</ul>
<p><b>주요 변동 라인 관찰</b>:</p>
<ul>
<li><b>수취보험료 규모</b>: 삼성생명 418천억 (압도) &gt; 삼성화재 358천억 &gt; 한화생명 167천억 &gt; 미래에셋 69천억</li>
<li><b>지급보험금 / 수취보험료 비율</b>: 미래에셋 124% (지급 86 / 수취 69) — 자사 지급률 상대적 높음</li>
<li><b>보험취득CF 지급</b>: 미래에셋 18.1조 = BS 27조의 67% — 자산 대비 매우 큰 비중</li>
<li><b>금융손익(PL)</b>: 삼성생명 +74천억 (이익), 미래에셋 −22천억 (손실), 손보 −4~13천억</li>
<li><b>위험조정 변동</b>: 미래에셋 −191억 (절대값 최소) — RA 변동 가장 작음</li>
</ul>"""

# 기존 §5-G 영역 교체 (§5-G 시작부터 §6 시작 전까지)
import re
# 기존 §5-G ~ §6 직전 영역 정확히 식별: <h2>5-G.</h2>부터 다음 <h2>까지
pattern_g = re.compile(r'<h2>5-G\..*?(?=<h2>6\.)', re.DOTALL)
html = pattern_g.sub(new_g_block + "\n", html, count=1)

# ─── 2) §5-F-(연도별) 연도별 분해 — 기존 §5-F 다음에 삽입 ───
BUCKETS = ["≤1년","1-2년","2-3년","3-4년","4-5년","5-10년","10-15년","15-20년","20-25년","25-30년",">30년"]

f_year_block = '<h3>5-F-(연도별) 위험보험료 / 예상보험금 / 예정·예상유지비 — Maturity 분해 (FY2025 별도, 억원)</h3>\n<p>각 metric을 만기 구간별로 분해. 보험계약 기간별 부채 인식 패턴 비교:</p>\n'

for metric in ["위험보험료", "예상보험금", "예정유지비", "예상유지비"]:
    data = acturial_year[metric]
    f_year_block += f'<h4>{metric}</h4>\n<div class="table-wrap"><table><thead><tr><th>회사</th>'
    for b in BUCKETS:
        f_year_block += f'<th>{b}</th>'
    f_year_block += '<th>합계</th></tr></thead><tbody>'
    for cik in PEER_CIKS:
        row = data.get(cik, {})
        cls = "self" if cik == "00112332" else ""
        f_year_block += f'<tr class="{cls}"><td class="company">{PEER_NAMES[cik]}</td>'
        total = 0
        for b in BUCKETS:
            v = row.get(b)
            if v is None or abs(v) < 1e6:
                f_year_block += '<td class="num">—</td>'
            else:
                f_year_block += f'<td class="num">{v/1e8:,.0f}</td>'
                total += v
        f_year_block += f'<td class="num"><b>{total/1e8:,.0f}</b></td></tr>'
    f_year_block += '</tbody></table></div>\n'

f_year_block += """<p><b>핵심 인사이트</b>:</p>
<ul>
<li><b>≤1년 위험보험료</b>: 미래에셋 미공시 (5년 이내 통합 보고). DB손보 11.5조 = 가장 단기 비중 큼</li>
<li><b>30년 초과 위험보험료</b>: 한화생명 76.5조 / 미래에셋 6.7조 — 한화가 자사 약 11배 (장기 부채 비중 격차)</li>
<li><b>예정유지비 vs 예상유지비 (사업비 마진)</b>:
    <ul>
    <li>미래에셋: 예정 20,523 vs 예상 39,691 — <b>예상이 예정의 1.93배</b> ⚠ 사업비 가정 격차</li>
    <li>한화생명: 예정 317,564 vs 예상 141,024 — 예정이 예상의 2.25배 (보수적 가정)</li>
    <li>현대해상: 예정 183,724 vs 예상 105,860 — 예정이 예상의 1.74배</li>
    <li>DB손보: 예정 561,663 vs 예상 272,157 — 예정이 예상의 2.06배</li>
    </ul>
</li>
</ul>
"""

# 기존 §5-F 본문(현재 §5-F는 4개사 매핑 표) 다음에 삽입 — §5-G 시작 전 위치
# Insert before "<h2>5-G."
html = html.replace('<h2>5-G. 변동표', f_year_block + '<h2>5-G. 변동표')

# ─── 3) §5-H 사업비 영역 — §6 IFRS17 가정 시작 전 삽입 ───
h_block = """<h2>5-H. 사업비 영역 — 손익 기반 (FY2025 별도, DI320000)</h2>
<p>판매비·관리비, 보험영업비용, 투자영업비용 등 사업비 항목 8개사 비교. 사업비율 = (판관비 + 보험영업비용) / 보험수익:</p>
<div class="table-wrap">
<table>
<thead><tr><th>회사</th><th>구분</th><th>판관비</th><th>보험영업비용</th><th>투자영업비용</th><th>기타보험비용</th><th>기타투자비용</th><th>영업외비용</th><th>보험수익</th><th>사업비율</th></tr></thead>
<tbody>
"""
for cik in PEER_CIKS:
    r = opex[cik]
    cls = "self" if cik == "00112332" else ""
    def f(v): return f"{v/1e8:,.0f}억" if v else "—"
    er = r.get("사업비율")
    er_cls = ""
    er_str = "—"
    if er is not None:
        if er <= 95: er_cls = " pass-cell"
        elif er <= 100: er_cls = " warn-cell"
        else: er_cls = " fail-cell"
        er_str = f"<b>{er:.1f}%</b>"
    h_block += f'<tr class="{cls}"><td class="company">{PEER_NAMES[cik]}</td><td>{SECTORS[cik]}</td>'
    for k in ["판매비와관리비","보험영업비용","투자영업비용","기타보험영업비용","기타투자영업비용","영업외비용","보험수익"]:
        h_block += f'<td class="num">{f(r[k])}</td>'
    h_block += f'<td class="num{er_cls}">{er_str}</td></tr>'
h_block += """</tbody></table></div>

<p><b>사업비율 ranking (사업비 효율, 낮을수록 좋음)</b>:</p>
<ol>
<li><b>미래에셋 93.7% — 동업사 중 최저 (가장 효율적)</b> ✓ 자사 본업 운영효율 우위</li>
<li>동양생명 94.2%</li>
<li>삼성생명 95.2%</li>
<li>삼성화재 96.8%</li>
<li>한화생명 97.0%</li>
<li>DB손보 98.4%</li>
<li><b>현대해상 101.4%</b> ⚠ — 사업비가 보험수익 초과</li>
<li><b>한화손보 103.8%</b> ⚠ — 사업비가 보험수익 크게 초과</li>
</ol>

<p><b>사업비 구조 (생보 vs 손보)</b>:</p>
<ul>
<li><b>생보</b>: 투자영업비용이 보험영업비용보다 큼 — 자산운용 의존도. 미래에셋 38,735 vs 9,921억 (3.9배), 삼성생명 202,061 vs 88,139억 (2.3배)</li>
<li><b>손보</b>: 보험영업비용 절대값 압도 — 손해율·보상비. 삼성화재 176,901 vs 39,266억 (4.5배)</li>
</ul>

<div class="conclusion">
<h4>📌 자사 사업비 시사점</h4>
<ul>
<li><b>사업비율 93.7% — 8개사 중 최저</b>. 본업 효율 우위. 동업사 평균 97.6% 대비 −3.9%p 양호.</li>
<li><b>그러나 §5-F-(연도별) 검증: 예상유지비/예정유지비 = 1.93배</b> — 예상 사업비가 예정의 거의 2배. <b>사업비 절대 효율은 좋으나 가정 보수성은 낮음</b>. 예정사업비율 갱신 점검 권장.</li>
<li><b>판관비 절대값 207억</b> — 자사 규모 감안시 적정 (BS 부채 27조의 0.077%)</li>
<li><b>투자영업비용 38,735억</b> — 보험영업비용 9,921억의 약 4배. 자산운용 비중 큼 (VFA 위주 사업 mix와 일관)</li>
</ul>
</div>
"""

# §6 IFRS17 가정 앞에 §5-H 삽입
html = html.replace('<h2>6. IFRS17 회계가정 적용 사항</h2>', h_block + '<h2>6. IFRS17 회계가정 적용 사항</h2>')

report.write_text(html, encoding="utf-8")
print(f"updated {report} ({len(html):,} bytes)")
