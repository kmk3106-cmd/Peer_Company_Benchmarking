"""§5-G 잔액 + §5-F 연도별 + §5-H 사업비 영역 추가."""
from __future__ import annotations
import json
from pathlib import Path

R = Path("report")
report = R / "종합보고서_FY2025.html"
html = report.read_text(encoding="utf-8")

# Load updated data
line_matrix = json.loads((R / "line_values_matrix.json").read_text(encoding="utf-8"))
acturial_year = json.loads((R / "actuarial_by_year.json").read_text(encoding="utf-8"))
opex = json.loads((R / "operating_expense_results.json").read_text(encoding="utf-8"))

PEER_CIKS = ["00112332", "00126256", "00113058", "00117267",
             "00139214", "00164973", "00159102", "00135917"]
PEER_NAMES = {"00112332":"미래에셋","00126256":"삼성생명","00113058":"한화생명","00117267":"동양생명",
              "00139214":"삼성화재","00164973":"현대해상","00159102":"DB손보","00135917":"한화손보"}
SECTORS = {"00112332":"생보","00126256":"생보","00113058":"생보","00117267":"생보",
           "00139214":"손보","00164973":"손보","00159102":"손보","00135917":"손보"}

# ─────── 1) §5-G 새 매트릭스 (기시/기말 포함) ───────
LINE_ORDER = list(line_matrix.keys())

new_g = """
<h2>5-G. 변동표 + 기시/기말 잔액 — 8개사 횡단비교 (FY2025 별도·발행, 단위 억원)</h2>
<p>기시(2024-12-31)·기말(2025-12-31) 잔액 + 17 변동 라인. 잔액 행은 노란색 강조:</p>
<div class="table-wrap">
<table>
<thead><tr><th>라인</th>"""
for cik in PEER_CIKS:
    cls = "self" if cik == "00112332" else ""
    new_g += f'<th class="{cls}">{PEER_NAMES[cik]}</th>'
new_g += '</tr></thead><tbody>'

for line in LINE_ORDER:
    row = line_matrix[line]
    is_balance = "잔액" in line
    tr_cls = ' style="background:#fff7e0;font-weight:600"' if is_balance else ""
    new_g += f'<tr{tr_cls}><td class="label">{line}</td>'
    for cik in PEER_CIKS:
        v = row.get(cik)
        cls = "num self" if cik == "00112332" else "num"
        if v is None or abs(v) < 1e8:
            new_g += f'<td class="{cls}">—</td>'
        else:
            new_g += f'<td class="{cls}">{v/1e8:+,.0f}</td>'
    new_g += '</tr>'
new_g += '</tbody></table></div>'
new_g += """
<p><b>잔액 변동 핵심</b>:</p>
<ul>
<li><b>자사 미래에셋</b>: 262,484 → 269,967 (<b>+7,483억, +2.9%</b>) — 부채 소폭 증가</li>
<li>삼성생명 2,021,563 → 2,008,463 (−13,100, −0.6%) — 안정</li>
<li>한화생명 971,522 → 969,358 (−2,164, −0.2%) — 거의 보합</li>
<li>삼성화재 516,095 → 487,348 (−28,747, −5.6%) — 부채 감소 최대</li>
<li>한화손보 151,976 → 153,485 (+1,509, +1.0%) — 소폭 증가</li>
</ul>"""

# 기존 §5-G 영역 교체
import re
old_g_pattern = r'<h2>5-G\..*?</ul>\s*'
html = re.sub(old_g_pattern, new_g, html, count=1, flags=re.DOTALL)

# ─────── 2) §5-F 연도별 분해 (새 섹션, 기존 §5-F 다음에 추가) ───────
BUCKETS = ["≤1년","1-2년","2-3년","3-4년","4-5년","5-10년","10-15년","15-20년","20-25년","25-30년",">30년"]

new_f_year = """
<h3>5-F-(연도별) 위험보험료 / 예상보험금 / 예정·예상유지비 — Maturity 분해 (FY2025 별도, 억원)</h3>
<p>각 metric을 만기(remaining coverage) 구간별로 분해. 보험계약 기간별 부채 인식 패턴 비교:</p>
"""

for metric in ["위험보험료", "예상보험금", "예정유지비", "예상유지비"]:
    data = acturial_year[metric]
    new_f_year += f'<h4>{metric}</h4>\n<div class="table-wrap"><table><thead><tr><th>회사</th>'
    for b in BUCKETS:
        new_f_year += f'<th>{b}</th>'
    new_f_year += '<th>합계</th></tr></thead><tbody>'
    for cik in PEER_CIKS:
        row = data.get(cik, {})
        cls = "self" if cik == "00112332" else ""
        new_f_year += f'<tr class="{cls}"><td class="company">{PEER_NAMES[cik]}</td>'
        total = 0
        for b in BUCKETS:
            v = row.get(b)
            if v is None or abs(v) < 1e6:
                new_f_year += '<td class="num">—</td>'
            else:
                new_f_year += f'<td class="num">{v/1e8:,.0f}</td>'
                total += v
        new_f_year += f'<td class="num"><b>{total/1e8:,.0f}</b></td></tr>'
    new_f_year += '</tbody></table></div>\n'

new_f_year += """<p><b>핵심 인사이트</b>:</p>
<ul>
<li><b>≤1년 위험보험료</b>: 미래에셋 미공시 → 단기 단위 분해 안 함 (10년 이내 통합). DB손보 11.5조 = 압도적 단기 비중</li>
<li><b>30년 초과 비중</b>: 한화생명 76조 / 미래에셋 6.7조 — 한화가 자사 11배 (장기 부채 비중 격차)</li>
<li><b>예정유지비 vs 예상유지비 차이</b> (사업비 마진):
    <ul>
    <li>미래에셋: 예정 20,523억 vs 예상 39,691억 — <b>예상이 예정의 1.93배 (사업비 가정 격차 큼)</b></li>
    <li>한화생명: 예정 31.8조 vs 예상 14.1조 — 예정이 예상의 2.25배 (보수적 사업비 가정)</li>
    <li>현대해상: 예정 18.4조 vs 예상 10.6조 — 예정이 예상의 1.73배</li>
    </ul>
</li>
</ul>"""

# §5-F 끝나는 곳 (5-G 시작 전)에 5-F-(연도별) 삽입
# §5-F 다음 §5-G 패턴 찾기
html = html.replace('<h2>5-G.', new_f_year + '<h2>5-G.')

# ─────── 3) §5-H 사업비 영역 (§5-G 뒤에 추가) ───────
new_h = """
<h2>5-H. 사업비 영역 — 손익 기반 (FY2025 별도, DI320000)</h2>
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
    if er is not None:
        if er <= 95: er_cls = " pass-cell"
        elif er <= 100: er_cls = " warn-cell"
        else: er_cls = " fail-cell"
    er_str = f"<b>{er:.1f}%</b>" if er else "—"
    new_h += f'<tr class="{cls}"><td class="company">{PEER_NAMES[cik]}</td><td>{SECTORS[cik]}</td>'
    for k in ["판매비와관리비","보험영업비용","투자영업비용","기타보험영업비용","기타투자영업비용","영업외비용","보험수익"]:
        new_h += f'<td class="num">{f(r[k])}</td>'
    new_h += f'<td class="num{er_cls}">{er_str}</td></tr>'
new_h += '</tbody></table></div>'

new_h += """
<p><b>사업비율 ranking (사업비 효율)</b>:</p>
<ul>
<li><b>미래에셋 93.7% — 동업사 중 최저 (가장 효율적)</b> ✓ 자사 본업 운영효율 우위</li>
<li>동양생명 94.2% (2위)</li>
<li>삼성생명 95.2%, 삼성화재 96.8%, 한화생명 97.0% (3~5위 — 양호)</li>
<li>DB손보 98.4%, <b>현대해상 101.4%</b> (사업비 > 보험수익 ⚠), <b>한화손보 103.8%</b> (사업비 > 보험수익 ⚠)</li>
</ul>

<p><b>구조 비교</b>:</p>
<ul>
<li><b>생보 vs 손보 사업비 구조</b>:
    <ul>
    <li>생보: 투자영업비용이 보험영업비용보다 큼 (자산운용 의존도). 미래에셋 38,735 vs 9,921억 (3.9배)</li>
    <li>손보: 보험영업비용이 절대값 압도. 삼성화재 보험영업비 176,901억 vs 투자영업비 39,266억</li>
    </ul>
</li>
<li><b>판관비 절대값</b>: 삼성생명 3,422억 (압도) &gt; 한화생명 1,178억 &gt; 미래에셋 207억 (자사 절대 규모 작음)</li>
</ul>

<div class="conclusion">
<h4>📌 자사 사업비 시사점</h4>
<ul>
<li><b>사업비율 93.7% — 8개사 중 최저</b>. 본업 효율 우위. 동업사 평균 97.6% 대비 -3.9%p 양호.</li>
<li><b>단, §5-F-(연도별) 결과: 예상유지비/예정유지비 = 1.93배</b> — 예상 사업비가 예정의 거의 2배. 사업비 절대 효율은 좋으나 <b>가정 보수성은 낮음</b>. 예정사업비율 갱신 점검 필요.</li>
<li><b>판관비 절대값은 작음 (207억)</b> — 자사 규모 감안시 적정. BS 부채 27조 대비 판관비 0.077%</li>
</ul>
</div>
"""

# §5-G 끝나는 곳에 §5-H 삽입 (§6 시작 전)
html = html.replace('<h2>6. 자사(미래에셋생명) 인사이트</h2>',
                     new_h + '<h2>7. 자사(미래에셋생명) 인사이트</h2>')

# 기존 §6 (IFRS17 가정)이 있다면 §6은 그대로 두기 - 사실 § 번호 충돌. 정리:
# §6. IFRS17 회계가정  (이미 있음)
# §7. 자사 인사이트 (방금 §7로 옮김)
# §8. 한계 (이미 있음)
# 근데 보고서에 §6. IFRS17 회계가정 + §6. 자사 인사이트 둘 다 §6 — 충돌
# 확인 필요
# 일단 §7로 옮긴 자사 인사이트는 §7 유지. §6 IFRS17 가정 그대로.
# 한계 §8. 분석 한계 그대로 유지
# §7. 자사 인사이트 (방금 §6에서 §7로 이동) ↔ 한계 §8과 충돌 없음
# 다만 IFRS17 가정 §6과 자사 인사이트 §7 사이 순서가 맞는지 확인.

# 한계 §7 → §9로 옮기기? 아니, 일단 그대로 두자.
# 현재 흐름: §6 IFRS17 가정 → §7 자사 인사이트 → §8 한계 (정상)

report.write_text(html, encoding="utf-8")
print(f"updated {report} ({len(html):,} bytes)")
