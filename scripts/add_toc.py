"""종합보고서에 목차(TOC) + 플로팅 네비게이션 추가.

기능:
1. 모든 <h2>에 id 부여 (anchor)
2. §1 다음에 카드형 TOC 삽입
3. 우상단 sticky 메뉴 버튼 (모바일 친화)
4. 우하단 ↑ Top 버튼
"""
from __future__ import annotations
import re
from pathlib import Path

report = Path("report/종합보고서_FY2025.html")
html = report.read_text(encoding="utf-8")

# 1) 모든 <h2>에 id 부여 + TOC 항목 수집
toc_items = []  # [(id, title, level), ...]

def slugify(text: str) -> str:
    """제목 → URL-safe id."""
    s = re.sub(r"<[^>]+>", "", text)  # HTML 태그 제거
    s = re.sub(r"\s+", "-", s.strip())
    s = re.sub(r"[^\w가-힣\-]", "", s)  # 한글·영숫자·- 만
    return s[:50]


def h2_replacer(m):
    title = m.group(1)
    sid = "sec-" + slugify(title)
    toc_items.append((sid, title, 2))
    return f'<h2 id="{sid}">{title}</h2>'


def h3_replacer(m):
    title = m.group(1)
    sid = "sec-" + slugify(title)
    toc_items.append((sid, title, 3))
    return f'<h3 id="{sid}">{title}</h3>'


html = re.sub(r"<h2>(.*?)</h2>", h2_replacer, html)
html = re.sub(r"<h3>(.*?)</h3>", h3_replacer, html)

# 2) TOC HTML 생성
toc_html = """
<!-- TOC: 책갈피 -->
<div class="toc-container">
  <button class="toc-toggle" onclick="document.getElementById('toc-list').classList.toggle('open');">
    📑 목차 보기/숨기기
  </button>
  <nav id="toc-list" class="toc-list open">
"""
for sid, title, level in toc_items:
    clean_title = re.sub(r"<[^>]+>", "", title)
    indent_class = "toc-h3" if level == 3 else "toc-h2"
    toc_html += f'    <a href="#{sid}" class="{indent_class}">{clean_title}</a>\n'

toc_html += """  </nav>
</div>
"""

# 3) §1 위에 TOC 삽입 (검토결론 직전)
# 첫 <h2 id="sec-1...">검토 결론</h2> 앞에 삽입
match = re.search(r'<h2 id="sec-[^"]*">1\. 검토 결론</h2>', html)
if match:
    html = html[:match.start()] + toc_html + html[match.start():]
else:
    # fallback: <body> 다음에
    html = html.replace("<body>", "<body>\n" + toc_html)

# 4) 플로팅 Top 버튼 (body 마지막)
floating_btn = """
<a href="#" class="back-to-top" title="맨 위로">↑</a>
"""
html = html.replace("</body>", floating_btn + "\n</body>")

# 5) CSS 추가 (style 블록 내)
new_css = """
  /* ─── 목차 (TOC) ─── */
  .toc-container {
    background: #fff; border: 1px solid #ccc; border-radius: 8px;
    padding: 14px 18px; margin: 16px 0 24px;
    box-shadow: 0 2px 6px rgba(0,0,0,0.04);
  }
  .toc-toggle {
    background: #4a76d8; color: white; border: none;
    padding: 8px 14px; border-radius: 6px; font-size: clamp(10pt, 2.5vw, 12pt);
    cursor: pointer; font-weight: 600; margin-bottom: 8px;
  }
  .toc-toggle:hover { background: #1a3870; }
  .toc-list {
    display: none; margin-top: 10px;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 4px 12px;
  }
  .toc-list.open { display: grid; }
  .toc-list a {
    color: #1a3870; text-decoration: none; padding: 6px 8px;
    border-radius: 4px; font-size: clamp(9.5pt, 2.2vw, 11pt);
    border-left: 3px solid transparent; line-height: 1.4;
  }
  .toc-list a:hover { background: #f0f5fb; border-left-color: #4a76d8; }
  .toc-list a.toc-h2 { font-weight: 600; }
  .toc-list a.toc-h3 { padding-left: 24px; color: #555; font-size: clamp(9pt, 2vw, 10.5pt); }

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

  /* anchor 점프시 sticky header offset */
  h2[id], h3[id] { scroll-margin-top: 16px; }

  @media (max-width: 600px) {
    .back-to-top { bottom: 16px; right: 16px; width: 44px; height: 44px; font-size: 20px; }
    .toc-list { grid-template-columns: 1fr; }
  }
"""

# style 블록 끝(`</style>`) 직전에 새 CSS 삽입
html = html.replace("</style>", new_css + "</style>")

report.write_text(html, encoding="utf-8")
print(f"updated {report} ({len(html):,} bytes)")
print(f"TOC 항목 {len(toc_items)}개 추가:")
for sid, title, level in toc_items:
    indent = "  " if level == 3 else ""
    clean = re.sub(r"<[^>]+>", "", title)[:70]
    print(f"  {indent}#{sid:<40s}  {clean}")
