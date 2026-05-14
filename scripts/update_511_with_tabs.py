"""§5.11 — 8개사 회사 탭 selector 보고서 교체."""
from __future__ import annotations
import json, re
from pathlib import Path

R = Path("report")
data = json.loads((R / "peer_assumption_final.json").read_text(encoding="utf-8"))

PEER_CIKS = ["00112332", "00126256", "00113058", "00117267",
             "00139214", "00164973", "00159102", "00135917"]

# 탭 버튼 + 패널 HTML
tab_buttons = '<div class="peer-tabs">'
for i, cik in enumerate(PEER_CIKS):
    name = data[cik]["name"]
    status = data[cik]["status"]
    active_cls = " active" if i == 0 else ""
    badge = "" if status == "extracted" else ' <span class="badge-na">미공시</span>'
    tab_buttons += f'<button class="peer-tab{active_cls}" onclick="showPeerTab(\'{cik}\')">{name}{badge}</button>'
tab_buttons += '</div>'

tab_panels = ''
for i, cik in enumerate(PEER_CIKS):
    info = data[cik]
    active_cls = " active" if i == 0 else ""
    tab_panels += f'<div id="peer-{cik}" class="peer-panel{active_cls}">'
    tab_panels += f'<h3>{info["name"]} (entity{cik})</h3>'

    if info["status"] == "not_disclosed":
        tab_panels += '<p class="warn-text">❌ 가정변경 element 미공시 — 사업보고서 원본 XBRL 에서 정확 라벨 매치 없음.</p>'
        tab_panels += '</div>'
        continue

    tab_panels += '<div class="table-wrap"><table>'
    tab_panels += '<thead><tr><th rowspan="2">라인</th><th colspan="3">별도 (Separate)</th><th colspan="3">연결 (Consolidated)</th></tr>'
    tab_panels += '<tr><th>BEL</th><th>RA</th><th>CSM</th><th>BEL</th><th>RA</th><th>CSM</th></tr></thead><tbody>'

    def f(v):
        if v is None: return "—"
        return f"{v/1e8:+,.0f}"

    has_sep = has_cons = False
    for line in info["lines"]:
        s = line["sep"]; c = line["cons"]
        if any(v is not None for v in s.values()): has_sep = True
        if any(v is not None for v in c.values()): has_cons = True
        is_total = "총합" in line["label"]
        tr_attr = ' style="background:#f0f5fb;font-weight:600"' if is_total else ""
        tab_panels += f'<tr{tr_attr}><td class="label">{line["label"]}</td>'
        tab_panels += f'<td class="num">{f(s["BEL"])}</td><td class="num">{f(s["RA"])}</td><td class="num">{f(s["CSM"])}</td>'
        tab_panels += f'<td class="num">{f(c["BEL"])}</td><td class="num">{f(c["RA"])}</td><td class="num">{f(c["CSM"])}</td>'
        tab_panels += '</tr>'
    tab_panels += '</tbody></table></div>'

    notes = []
    if not has_sep: notes.append("⚠ 별도(Separate) 미공시 — 연결만 보고")
    if not has_cons: notes.append("⚠ 연결(Consolidated) 미공시")

    # 회사별 코멘트
    if cik == "00112332":
        notes.append("✓ 6개 라인 분해 (해지율·위험율·예정율·기타 + 손실요소·보유물량). Table 형태 별도 공시")
    elif cik == "00126256":
        notes.append("⚠ 단일 element만 보고. 가정 항목별 분해 미공시 (별도·연결 모두 0)")
    elif cik == "00113058":
        notes.append("✓ 5개 라인 분해 — 사업비율 가정변경 분해. 별도 < 연결 (자회사 영향)")
    elif cik == "00164973":
        notes.append("✓ 위험률 가정변경 BEL +12,986억 = 동업사 중 최대 (위험률 큰 폭 상향)")
    elif cik == "00159102":
        notes.append("✓ 가정변경 총합 BEL +17,061 = 동업사 최대. 사업비율 가정 +11,193억 상향")
    elif cik == "00135917":
        notes.append("✓ CSM 조정하는 4개 가정 분해 (한화손보 고유 구조)")

    if notes:
        tab_panels += '<ul class="note-list">'
        for n in notes:
            tab_panels += f'<li>{n}</li>'
        tab_panels += '</ul>'
    tab_panels += '</div>'

# Cross-table: 가정변경 총합 (BEL) 횡단비교
cross_table = '<h3>📊 가정변경 효과 횡단 비교 — 가정변경 총합 BEL 영향 (별도, 억원)</h3>'
cross_table += '<p>가정변경으로 BEL이 얼마나 증가했는지 (CSM이 동일 금액 흡수). BEL ↑ = 가정 보수적 갱신:</p>'
cross_table += '<div class="table-wrap"><table><thead><tr><th>회사</th><th>해지율</th><th>위험률</th><th>사업비율/예정율</th><th>기타</th><th>총합 BEL ↑</th></tr></thead><tbody>'

# 라인별 BEL 합산
def get_line_bel(cik, label_pattern):
    if data[cik]["status"] != "extracted": return None
    for line in data[cik]["lines"]:
        if label_pattern in line["label"]:
            return line["sep"]["BEL"]
    return None


def f2(v):
    if v is None: return "—"
    return f"{v/1e8:+,.0f}억"


for cik in PEER_CIKS:
    info = data[cik]
    name = info["name"]
    if info["status"] != "extracted":
        cross_table += f'<tr><td class="company">{name}</td><td colspan="5" class="num">(미공시)</td></tr>'
        continue
    h = get_line_bel(cik, "해지율")
    r_ = get_line_bel(cik, "위험율") or get_line_bel(cik, "위험률")
    e = get_line_bel(cik, "사업비율") or get_line_bel(cik, "예정율")
    o = get_line_bel(cik, "기타")
    t = get_line_bel(cik, "총합") or get_line_bel(cik, "효과 (단일)")
    cls = "self" if cik == "00112332" else ""
    cross_table += f'<tr class="{cls}"><td class="company">{name}</td>'
    cross_table += f'<td class="num">{f2(h)}</td><td class="num">{f2(r_)}</td>'
    cross_table += f'<td class="num">{f2(e)}</td><td class="num">{f2(o)}</td>'
    cross_table += f'<td class="num"><b>{f2(t)}</b></td></tr>'

cross_table += '</tbody></table></div>'
cross_table += """<p><b>핵심 시그널</b>:</p>
<ul>
<li><b>가정변경 총합 BEL ↑ ranking</b>: DB손보 +17,061억 &gt; 현대해상 +11,657 &gt; 미래에셋 +8,225 (4개 합) &gt; 한화생명 +4,864 &gt; 한화손보 +2,487</li>
<li><b>모든 회사 BEL ↔ CSM 정확히 대칭</b> (CSM이 가정 충격 흡수 — IFRS17 §103 표준)</li>
<li><b>사업비율 가정변경</b>: 회사별 부호 다름. 한화생명·현대·한화손보 BEL ↓ (사업비율 하향), DB손보 BEL ↑ (사업비율 상향)</li>
<li><b>위험률 가정변경 ranking</b>: 현대해상 +12,986 (최대) &gt; DB손보 -6,889 (역방향) &gt; 한화손보 +2,972 &gt; 미래에셋 +2,317</li>
<li><b>미공시 회사</b>: 동양생명·삼성화재 — 가정변경 element 별도 분해 안 함 (CSM 조정 추정변동 통합 보고만)</li>
</ul>"""

# CSS (탭 스타일 + 배지)
css = """
  /* 회사 탭 selector */
  .peer-tabs { display: flex; flex-wrap: wrap; gap: 6px; margin: 14px 0 6px; padding-bottom: 8px; border-bottom: 2px solid #ddd; }
  .peer-tab {
    background: #f0f0f0; border: 1px solid #ccc; color: #444;
    padding: 7px 13px; border-radius: 5px 5px 0 0;
    font-size: clamp(9.5pt, 2.3vw, 11pt); font-weight: 600;
    cursor: pointer; transition: all 0.15s;
  }
  .peer-tab:hover { background: #e0e8f5; color: #1a3870; }
  .peer-tab.active { background: #1a3870; color: white; border-color: #1a3870; }
  .peer-panel { display: none; padding-top: 10px; }
  .peer-panel.active { display: block; }
  .badge-na { background: #f4e6e6; color: #8c2424; padding: 1px 5px; border-radius: 3px; font-size: 0.85em; }
  .warn-text { color: #8c2424; background: #fdf3f3; padding: 8px 12px; border-radius: 4px; }
  .note-list { font-size: clamp(9.5pt, 2.1vw, 11pt); color: #555; margin: 8px 0 0; padding-left: 22px; }
"""

# 스크립트 (탭 전환)
js = """
<script>
function showPeerTab(cik) {
  document.querySelectorAll('.peer-tab').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.peer-panel').forEach(p => p.classList.remove('active'));
  event.target.classList.add('active');
  document.getElementById('peer-' + cik).classList.add('active');
}
</script>
"""

# 새 §5.11 블록
new_511 = f"""<h2 id="sec-5-11-계리적가정-보험부채-변동내역-8개사">5.11 계리적가정에 의한 보험부채 변동내역 — 8개사 (정확 search)</h2>

<div class="conclusion">
<h4>📋 8개사 검증 결과</h4>
<ul>
<li><b>가정변경 분해 공시 6개사</b>: 미래에셋·삼성생명·한화생명·현대해상·DB손보·한화손보</li>
<li><b>미공시 2개사</b>: 동양생명·삼성화재 — 가정변경 element 별도 보고 안 함</li>
<li>회사마다 element 명명·분해 방식 다름. 각사 entity 확장 element 정확 매칭으로 추출 (유추 X)</li>
<li>회사 탭 클릭하여 각사 상세 보기. 마지막에 횡단 비교표 (총합 BEL) 제공</li>
</ul>
</div>

{tab_buttons}
{tab_panels}
{cross_table}
{js}
"""

# 기존 §5.11 통째 교체
report = R / "종합보고서_FY2025.html"
html = report.read_text(encoding="utf-8")
old_pattern = re.compile(r'<h2[^>]*>5\.11.*?(?=<h2[^>]*>5\.12)', re.DOTALL)
html = old_pattern.sub(new_511 + "\n", html, count=1)

# CSS 추가 (style 닫기 직전)
html = html.replace("</style>", css + "</style>")

report.write_text(html, encoding="utf-8")
print(f"updated {report} ({len(html):,} bytes)")
