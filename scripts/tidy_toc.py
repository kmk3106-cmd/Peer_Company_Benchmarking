"""목차 정리: 5-B~J → 5.1~5.9 재명명 + h3 제외 + 그룹별 TOC."""
from __future__ import annotations
import re
from pathlib import Path

report = Path("report/종합보고서_FY2025.html")
html = report.read_text(encoding="utf-8")

# ─── 1) h2 제목 재명명 ───
RENAMES = [
    ("4-B. 식별된 7 role 차례 추출 결과", "4.1 식별된 7개 role 추출 결과"),
    ("5. 추출된 자료 — BEL/RA/CSM 잔액 비교 (8개사)", "5.1 BEL/RA/CSM 잔액 비교"),
    ("5-B. DI817105 잔액 — 미래에셋 5상품군 × LRC/LIC (BS 100% 검증)", "5.2 미래에셋 5상품군 × LRC/LIC (BS 100% 검증)"),
    ("5-C. 자산-부채 매칭 (DI818200, 8개사 완전 추출)", "5.3 자산-부채 매칭 (Coverage Ratio)"),
    ("5-D. CSM 만기별 인식 기대액 (DI817300, 7개사 정규화)", "5.4 CSM 만기별 인식 기대액"),
    ("5-E. 손보 4개사 상품군 mix (DI817105)", "5.5 손보 상품군 mix (장기·자동차·일반)"),
    ("5-F. 계리적 metric — 위험보험료·예상보험금·예정·예상유지비 (DI817305)", "5.6 계리적 metric (위험보험료·예상보험금·유지비)"),
    ("5-G. 변동표 + 기시/기말 잔액 × 8개사 횡단비교 (FY2025 별도·발행, 단위 억원)", "5.7 변동표 17 라인 + 잔액 횡단비교"),
    ("5-H. 사업비 영역 — 손익 기반 (FY2025 별도, DI320000)", "5.8 사업비 영역 (판관비·영업비)"),
    ("5-I. 예실차 (Expected vs Actual Claims) — 보험금 가정 정확도", "5.9 예실차 (Expected vs Actual Claims)"),
    ("5-J. CSM 변동 무브먼트 — 8개사 (FY2025 별도, 억원)", "5.10 CSM 변동 무브먼트"),
    ("6. IFRS17 회계가정 적용 사항", "6. IFRS17 회계가정 적용"),
    ("7. 자사(미래에셋생명) 인사이트", "7. 자사 (미래에셋생명) 인사이트"),
    ("8. 분석 한계 및 다음 단계", "8. 분석 한계·다음 단계"),
]
for old, new in RENAMES:
    html = html.replace(old, new)

# ─── 2) 기존 TOC 블록 통째 제거 ───
html = re.sub(r"<!-- TOC: 책갈피 -->\s*<div class=\"toc-container\">.*?</div>\s*",
              "", html, count=1, flags=re.DOTALL)

# ─── 3) h2/h3 anchor id 재생성 ───
def slugify(text: str) -> str:
    s = re.sub(r"<[^>]+>", "", text)
    s = re.sub(r"\s+", "-", s.strip())
    s = re.sub(r"[^\w가-힣\-]", "", s)
    return s[:60]


h2_items = []

def h2_replacer(m):
    title = m.group(1)
    sid = "sec-" + slugify(title)
    h2_items.append((sid, title))
    return f'<h2 id="{sid}">{title}</h2>'


def h3_replacer(m):
    title = m.group(1)
    sid = "sec-" + slugify(title)
    return f'<h3 id="{sid}">{title}</h3>'  # h3는 id 부여하되 TOC에는 노출 안 함


html = re.sub(r"<h2[^>]*>(.*?)</h2>", h2_replacer, html)
html = re.sub(r"<h3[^>]*>(.*?)</h3>", h3_replacer, html)

# ─── 4) 그룹별 TOC HTML 생성 ───
def find(prefix_list, items):
    return [(sid, t) for sid, t in items if any(t.startswith(p) for p in prefix_list)]


group_overview = find(["1.", "2.", "3.", "4.", "4.1"], h2_items)
group_extract = [(sid, t) for sid, t in h2_items if t.startswith("5.")]
group_conclusion = find(["6.", "7.", "8."], h2_items)


def render_group(items, with_indent=False):
    out = ""
    for sid, t in items:
        clean = re.sub(r"<[^>]+>", "", t)
        cls = "toc-sub" if with_indent and "." in clean[:4] else ""
        out += f'<a href="#{sid}" class="toc-item {cls}">{clean}</a>\n'
    return out


toc_html = """
<div class="toc-container">
  <button class="toc-toggle" onclick="document.getElementById('toc-list').classList.toggle('hidden');">
    📑 목차
  </button>
  <nav id="toc-list" class="toc-list">
    <div class="toc-group">
      <h4 class="toc-group-title">📋 개요·매핑</h4>
"""
toc_html += render_group(group_overview, with_indent=True)
toc_html += """    </div>
    <div class="toc-group">
      <h4 class="toc-group-title">📊 추출 자료 (5)</h4>
"""
toc_html += render_group(group_extract, with_indent=True)
toc_html += """    </div>
    <div class="toc-group">
      <h4 class="toc-group-title">📌 결론·한계</h4>
"""
toc_html += render_group(group_conclusion, with_indent=True)
toc_html += """    </div>
  </nav>
</div>
"""

# §1 위에 삽입
match = re.search(r'<h2 id="[^"]*">1\. 검토 결론</h2>', html)
if match:
    html = html[:match.start()] + toc_html + html[match.start():]

# ─── 5) CSS 갱신 (기존 .toc CSS 모두 제거 후 새로) ───
new_css = """
  /* ─── 목차 (TOC) — 그룹형 ─── */
  .toc-container {
    background: #fff; border: 1px solid #ddd; border-radius: 10px;
    padding: 16px 20px; margin: 16px 0 28px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
  }
  .toc-toggle {
    background: #1a3870; color: white; border: none;
    padding: 10px 16px; border-radius: 6px;
    font-size: clamp(10pt, 2.5vw, 12pt); font-weight: 600;
    cursor: pointer; margin-bottom: 4px;
  }
  .toc-toggle:hover { background: #4a76d8; }
  .toc-list {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    gap: 16px; margin-top: 14px;
  }
  .toc-list.hidden { display: none; }
  .toc-group {
    background: #f7f9fc; border-radius: 8px; padding: 10px 12px;
    border-left: 4px solid #4a76d8;
  }
  .toc-group-title {
    margin: 0 0 8px 0; font-size: clamp(10pt, 2.3vw, 11pt);
    color: #1a3870; font-weight: 700;
  }
  .toc-item {
    display: block; color: #333; text-decoration: none;
    padding: 5px 8px; border-radius: 4px;
    font-size: clamp(9.5pt, 2.1vw, 10.5pt); line-height: 1.5;
    border-left: 2px solid transparent;
  }
  .toc-item:hover {
    background: #fff; border-left-color: #4a76d8; color: #1a3870;
  }
  .toc-sub { padding-left: 14px; }

  /* anchor 점프 offset */
  h2[id], h3[id] { scroll-margin-top: 16px; }

  /* ─── 맨 위로 버튼 ─── */
  .back-to-top {
    position: fixed; bottom: 24px; right: 24px;
    width: 52px; height: 52px; border-radius: 50%;
    background: #1a3870; color: white;
    display: flex; align-items: center; justify-content: center;
    font-size: 24px; font-weight: 700; text-decoration: none;
    box-shadow: 0 4px 12px rgba(0,0,0,0.2);
    z-index: 1000; opacity: 0.85; transition: opacity 0.2s;
  }
  .back-to-top:hover { opacity: 1; background: #4a76d8; }

  @media (max-width: 600px) {
    .back-to-top { bottom: 16px; right: 16px; width: 44px; height: 44px; font-size: 20px; }
    .toc-list { grid-template-columns: 1fr; }
  }
"""

# 기존 TOC/back-to-top 관련 CSS 제거
html = re.sub(r"/\* ─── 목차 \(TOC\)[^\}]*\}.*?@media \(max-width: 600px\) \{[^\}]*\.toc-list[^\}]*\}\s*\}",
              "", html, flags=re.DOTALL)
# 기존에 추가한 CSS 블록 제거 시도 (back-to-top 등)
html = re.sub(r"  /\* ─── 목차[^*]*\*/[\s\S]*?    \.toc-list \{ grid-template-columns: 1fr; \}\s*\}",
              "", html, count=1)
html = re.sub(r"\s*\.back-to-top \{[^}]*\}\s*\.back-to-top:hover \{[^}]*\}", "", html)

# style 닫기 직전에 새 CSS 삽입
html = html.replace("</style>", new_css + "</style>")

report.write_text(html, encoding="utf-8")
print(f"updated {report} ({len(html):,} bytes)")
print(f"\nTOC: 3 그룹")
print(f"  개요·매핑 ({len(group_overview)}): {[t for _, t in group_overview]}")
print(f"  추출 자료 ({len(group_extract)}): {[t for _, t in group_extract]}")
print(f"  결론·한계 ({len(group_conclusion)}): {[t for _, t in group_conclusion]}")
