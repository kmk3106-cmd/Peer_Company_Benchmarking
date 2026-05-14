"""Step 4: 자료작성·비교가능성 종합 보고서 (HTML).

입력:
  - report/coverage_matrix.csv     (Step 1)
  - report/feasibility_summary.csv (Step 2)
  - report/feasibility_details.json (Step 2 detail)
  - report/line_crosstab.csv       (Step 3)
  - report/analytic_scope.json     (Step 3)

출력: report/feasibility_report.html
"""
from __future__ import annotations
import csv, json
from pathlib import Path
from datetime import date

R = Path("report")

# load all data
coverage = list(csv.DictReader((R / "coverage_matrix.csv").open(encoding="utf-8-sig")))
summary = list(csv.DictReader((R / "feasibility_summary.csv").open(encoding="utf-8-sig")))
crosstab = list(csv.DictReader((R / "line_crosstab.csv").open(encoding="utf-8-sig")))
details = json.loads((R / "feasibility_details.json").read_text(encoding="utf-8"))
scope = json.loads((R / "analytic_scope.json").read_text(encoding="utf-8"))

# Peers 8개
LIFE = ["00112332", "00126256", "00113058", "00117267"]
NONLIFE = ["00139214", "00164973", "00159102", "00135917"]
ALL_PEERS_8 = LIFE + NONLIFE
names = {cik: details[cik]["company"] for cik in ALL_PEERS_8}


def yn(v: str) -> str:
    return "✓" if v in ("Y", "True", "true", "1") else "·"


def cls(v: str) -> str:
    return "pass-cell" if v in ("Y", "True", "true", "1") else "fail-cell"


# ───────────────── Section 1: Coverage matrix (14 × 4) ─────────────────
roles_in_cov = ["DI817100", "DI817105", "DI817300", "DI817305"]
companies_cov = sorted(set(r["company"] for r in coverage))

def cov_row(comp, role):
    rec = next((r for r in coverage if r["company"]==comp and r["role"]==role), None)
    if not rec or int(rec["n_facts"]) == 0:
        return ('<td class="fail-cell">미보고</td>', False)
    has_sep = rec["has_sep"] == "1"
    has_lrc = rec["has_lrc_lic"] == "1"
    has_comp = rec["has_components"] == "1"
    badges = []
    if has_sep: badges.append('<span class="b sep">별도</span>')
    if has_lrc: badges.append('<span class="b lrc">LRC/LIC</span>')
    if has_comp: badges.append('<span class="b comp">BEL/RA/CSM</span>')
    return (f'<td class="pass-cell">{rec["n_facts"]} fact<br><small>{"".join(badges)}</small></td>', True)

cov_html = ['<table class="cov"><thead><tr><th>회사</th>']
for rc in roles_in_cov:
    cov_html.append(f'<th>{rc}</th>')
cov_html.append('</tr></thead><tbody>')
for comp in companies_cov:
    cov_html.append(f'<tr><td class="company">{comp}</td>')
    any_pass = False
    for rc in roles_in_cov:
        td, p = cov_row(comp, rc)
        cov_html.append(td)
        if p: any_pass = True
    cov_html.append('</tr>')
cov_html.append('</tbody></table>')


# ───────────────── Section 2: Feasibility summary (8개사) ─────────────────
sum2 = ['<table class="feas"><thead><tr>',
        '<th>회사</th><th>구분</th><th>TypesAxis 멤버수</th>',
        '<th colspan="6">5상품군 매핑 (생보 기준)</th>',
        '<th colspan="3">Components</th>',
        '<th>표준라인<br>보고율</th><th>BS 잔액(억)</th>',
        '</tr><tr><th></th><th></th><th></th>',
        '<th>사망</th><th>건강</th><th>연금</th><th>저축</th><th>기타</th><th>미분류</th>',
        '<th>BEL</th><th>RA</th><th>CSM</th><th></th><th></th></tr></thead><tbody>']
for s in summary:
    rep = s["lines_reported"]
    n_rep = int(rep.split("/")[0])
    rep_class = "pass-cell" if n_rep >= 12 else ("warn-cell" if n_rep >= 8 else "fail-cell")
    sum2.append(f'<tr><td class="company">{s["company"]}</td>')
    sum2.append(f'<td>{s["sector"]}</td>')
    sum2.append(f'<td class="num">{s["n_types"]}</td>')
    for k in ("사망","건강","연금","저축","기타","미분류"):
        v = int(s[k])
        c = "num" if v > 0 else "num zero"
        sum2.append(f'<td class="{c}">{v}</td>')
    for k in ("BEL","RA","CSM"):
        v = s[k] in ("True","true")
        sum2.append(f'<td class="{cls("Y" if v else "N")}">{yn("Y" if v else "N")}</td>')
    sum2.append(f'<td class="{rep_class} num">{rep}</td>')
    sum2.append(f'<td class="num">{int(s["BS_liability_억"]):,}</td>')
    sum2.append('</tr>')
sum2.append('</tbody></table>')


# ───────────────── Section 3: Line crosstab (21 × 8) ─────────────────
def name_label(cik): return names[cik]

cross_html = ['<table class="cross"><thead><tr><th rowspan="2">표준 라인</th>',
              '<th colspan="4" class="life">생보 4</th>',
              '<th colspan="4" class="nonlife">손보 4</th>',
              '<th rowspan="2">합계 (생/손)</th>',
              '</tr><tr>']
for cik in LIFE:
    cross_html.append(f'<th class="life">{name_label(cik)}</th>')
for cik in NONLIFE:
    cross_html.append(f'<th class="nonlife">{name_label(cik)}</th>')
cross_html.append('</tr></thead><tbody>')

for row in crosstab:
    line = row["line"]
    n_total = int(row["n_total"])
    n_life = int(row["n_life"])
    n_nonlife = int(row["n_nonlife"])
    row_class = "ct-pass" if n_total >= 6 else ("ct-mid" if n_total >= 3 else "ct-low")
    cross_html.append(f'<tr class="{row_class}"><td class="label">{line}</td>')
    for cik in LIFE + NONLIFE:
        v = row[names[cik]]
        cross_html.append(f'<td class="{cls(v)}">{yn(v)}</td>')
    cross_html.append(f'<td class="num"><b>{n_total}</b>/8 ({n_life}/{n_nonlife})</td></tr>')
cross_html.append('</tbody></table>')


# ───────────────── Section 4: 분류 (PASS/WARNING/REVIEW) ─────────────────
total_lines = len(crosstab)
n_pass = sum(1 for r in crosstab if int(r["n_total"]) >= 6)  # 75%+
n_warn = sum(1 for r in crosstab if 3 <= int(r["n_total"]) < 6)
n_review = sum(1 for r in crosstab if int(r["n_total"]) < 3)

pass_pct = n_pass / total_lines * 100
warn_pct = n_warn / total_lines * 100
review_pct = n_review / total_lines * 100


# ───────────────── HTML 조립 ─────────────────
html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>동업사 부채변동 비교 자료 작성 및 비교가능성 진단 보고서</title>
<style>
  body {{ font-family: "맑은 고딕", "Malgun Gothic", sans-serif; margin: 20px; color: #222; background: #fafafa; max-width: 1400px; }}
  h1 {{ font-size: 18pt; border-bottom: 2px solid #333; padding-bottom: 6px; margin-top: 28px; }}
  h2 {{ font-size: 14pt; border-left: 4px solid #4a76d8; padding-left: 8px; margin-top: 24px; color: #1a3870; }}
  h3 {{ font-size: 12pt; color: #555; margin-top: 18px; }}
  .meta {{ font-size: 9pt; color: #666; margin-bottom: 16px; }}
  .meta span {{ margin-right: 18px; }}

  .summary-cards {{ display: flex; gap: 12px; margin: 16px 0; }}
  .card {{ flex: 1; padding: 14px; border-radius: 6px; border: 1px solid #ccc; background: #fff; }}
  .card .label {{ font-size: 9pt; color: #666; }}
  .card .num {{ font-size: 20pt; font-weight: 600; margin-top: 4px; }}
  .card.pass {{ border-color: #4a9d4e; }}
  .card.pass .num {{ color: #2d7d31; }}
  .card.warn {{ border-color: #d8a44a; }}
  .card.warn .num {{ color: #946a18; }}
  .card.review {{ border-color: #d84a4a; }}
  .card.review .num {{ color: #8c2424; }}

  table {{ border-collapse: collapse; background: #fff; font-size: 10pt; margin: 8px 0; }}
  th, td {{ border: 1px solid #888; padding: 5px 8px; }}
  thead th {{ background: #e8eef5; text-align: center; font-weight: 600; }}
  thead th.life {{ background: #fde9e9; }}
  thead th.nonlife {{ background: #e3edfa; }}
  td.company {{ text-align: left; font-weight: 600; min-width: 110px; }}
  td.label {{ text-align: left; min-width: 180px; }}
  td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  td.num.zero {{ color: #aaa; }}
  td.pass-cell {{ background: #e6f4e7; text-align: center; color: #2d7d31; font-weight: 600; }}
  td.fail-cell {{ background: #f4e6e6; text-align: center; color: #8c2424; }}
  td.warn-cell {{ background: #faf4e2; text-align: center; color: #946a18; font-weight: 600; }}
  tr.ct-pass td.label {{ font-weight: 600; color: #2d7d31; }}
  tr.ct-mid td.label {{ color: #946a18; }}
  tr.ct-low td.label {{ color: #8c2424; }}

  .b {{ display: inline-block; padding: 1px 4px; border-radius: 3px; font-size: 8pt; margin-right: 2px; }}
  .b.sep {{ background: #d4e8d6; color: #1a5a1c; }}
  .b.lrc {{ background: #d4dff5; color: #1a3870; }}
  .b.comp {{ background: #ead5f0; color: #5a1a70; }}

  .recommend {{ background: #f0f5fb; border-left: 4px solid #4a76d8; padding: 12px 16px; margin: 12px 0; border-radius: 0 4px 4px 0; }}
  .recommend h4 {{ margin: 0 0 8px 0; color: #1a3870; }}
  .recommend ul {{ margin: 4px 0; padding-left: 22px; }}

  .footer-note {{ font-size: 9pt; color: #555; line-height: 1.55; margin-top: 24px; padding-top: 14px; border-top: 1px solid #ccc; }}
  .footer-note ol {{ margin: 4px 0; padding-left: 22px; }}
  .footer-note code {{ background: #f0f0f0; padding: 1px 4px; border-radius: 3px; font-size: 9pt; }}
</style>
</head>
<body>

<h1>동업사 부채변동 비교 자료 작성 및 비교가능성 진단 보고서</h1>
<div class="meta">
  <span><b>대상</b>: KOSPI 상장 보험사 14개사 (자사 미래에셋생명 포함)</span>
  <span><b>기간</b>: FY2025 (2025-01-01 ~ 2025-12-31)</span>
  <span><b>기준</b>: 별도(Separate) · 발행보험(Issued)</span>
  <span><b>작성일</b>: {date.today()}</span>
</div>

<h2>1. 검토 결론</h2>

<div class="summary-cards">
  <div class="card pass">
    <div class="label">자동 비교 가능 (PASS)</div>
    <div class="num">{n_pass} / {total_lines} 라인</div>
    <div class="label">{pass_pct:.0f}% — 6/8개사 이상 보고</div>
  </div>
  <div class="card warn">
    <div class="label">조건부 비교 (WARNING)</div>
    <div class="num">{n_warn} / {total_lines} 라인</div>
    <div class="label">{warn_pct:.0f}% — 3~5개사 보고</div>
  </div>
  <div class="card review">
    <div class="label">비교 곤란 (REVIEW)</div>
    <div class="num">{n_review} / {total_lines} 라인</div>
    <div class="label">{review_pct:.0f}% — 2개사 이하 보고</div>
  </div>
</div>

<div class="recommend">
  <h4>핵심 결론</h4>
  <ul>
    <li>KOSPI 상장 14개사 중 <b>8개사</b>가 DI817100 (보험계약부채 변동)을 별도·발행 기준으로 보고. 비상장 4개사(KB라이프·교보·신한·흥국)와 메리츠화재·흥국화재는 미보고 또는 잔액만 보고.</li>
    <li>8개사 전부 <b>BEL/RA/CSM components_axis 분해</b> 보고 → IFRS17 §103 횡단 비교 무난.</li>
    <li>8개사 전부 <b>TypesOfContractsAxis 상품군 분해</b> 보고하나, 생보는 사망/건강/연금/저축, 손보는 장기/자동차/일반으로 axis 정의가 다름 → 생보·손보 분리 비교 필요.</li>
    <li><b>{n_pass}개 표준 라인</b>이 6개사 이상 공통 보고 → 자동 비교 PASS 후보.</li>
    <li><b>{n_review}개 라인</b>은 2개사 이하 보고 → 수기확인 대상 또는 매핑 룰 보강 필요 (특히 OCI·위험조정·과거서비스).</li>
  </ul>
</div>

<h2>2. 자료 작성 여부 매트릭스 (14개사 × 4 role)</h2>
<p>DI817100/105 = 보험계약부채 변동·잔액 (원수), DI817300/305 = 보험계약 정보·CSM 만기분석.<br>
별도(Separate)·LRC/LIC·BEL/RA/CSM axis 보고 여부를 badge로 표시.</p>

{"".join(cov_html)}

<h2>3. 비교 가능한 8개사 상세 (Feasibility)</h2>

{"".join(sum2)}

<h3>5상품군 매핑 한계 — 손보의 경우</h3>
<p>손보는 <b>장기/자동차/일반/기타</b>가 본질 분해 — 5분류와 misfit. 보강 매핑 적용 시:</p>
<table class="feas">
<thead><tr><th>회사</th><th>장기</th><th>자동차</th><th>일반</th><th>기타</th><th>미분류</th></tr></thead>
<tbody>
<tr><td class="company">삼성화재</td><td class="num">1</td><td class="num">1</td><td class="num">1</td><td class="num zero">0</td><td class="num zero">0</td></tr>
<tr><td class="company">현대해상</td><td class="num">7</td><td class="num">1</td><td class="num">1</td><td class="num">1</td><td class="num">4</td></tr>
<tr><td class="company">DB손해보험</td><td class="num">6</td><td class="num">1</td><td class="num">1</td><td class="num">1</td><td class="num">3</td></tr>
<tr><td class="company">한화손해보험</td><td class="num">7</td><td class="num">1</td><td class="num">1</td><td class="num zero">0</td><td class="num zero">0</td></tr>
</tbody></table>

<h2>4. 라인별 cross-tab (21 표준 라인 × 8개사)</h2>
<p>각 셀: 회사가 해당 라인을 별도·발행 기준으로 보고했는지 여부. 합계 ≥ 6/8 → 자동 비교 후보 (초록), 3~5 → WARNING, &lt;3 → REVIEW.</p>

{"".join(cross_html)}

<h2>5. 비교검증 가용성 — 2가지 View</h2>

<div class="recommend">
<h4>View A · BEL/RA/CSM 분해 (IFRS17 §103)</h4>
<p><b>대상</b>: 8개사 전부 — BEL/RA/CSM 모두 ✓</p>
<p><b>비교 가능 단위</b>: 라인 × BEL/RA/CSM × 8개사</p>
<p><b>추천 계리 분석</b>:</p>
<ul>
  <li><b>기말 잔액 BEL/RA/CSM ratio</b> — 회사별 보수성·CSM 의존도 시그널</li>
  <li><b>CSM 증가율</b> — 신계약 효과 절대값·이익 발생 잠재력</li>
  <li><b>RA 비율</b> (RA / BEL) — 위험부담 수준 비교</li>
  <li><b>보험금융손익 BEL 영향 vs CSM 영향</b> — 자산-부채 매칭 품질</li>
</ul>
</div>

<div class="recommend">
<h4>View B · 상품군 분해 (TypesOfContractsAxis)</h4>
<p><b>대상</b>: 생보 4개사 / 손보 4개사 <b>분리 비교</b> (axis 정의 다름)</p>
<p><b>생보 5분류</b>: 사망 / 건강 / 연금 / 저축 / 기타</p>
<p><b>손보 4분류</b>: 장기 / 자동차 / 일반 / 기타</p>
<p><b>추천 계리 분석</b>:</p>
<ul>
  <li><b>생보</b>: 사망보장 비중, 변액(저축+연금) 비중, 보장성 vs 저축성 mix</li>
  <li><b>손보</b>: 장기:자동차:일반 비중, 손해율 차이 시그널</li>
  <li><b>공통</b>: 상품군별 LRC/LIC ratio (장기 부채 vs 단기 부채 구조)</li>
</ul>
</div>

<h2>6. 비교 불가 및 한계</h2>
<ul>
  <li><b>미보고 6개사</b>: 비상장 4개사(KB라이프·교보생명·신한라이프·흥국생명), 메리츠화재, 흥국화재(잔액만) — 비교 대상에서 제외.</li>
  <li><b>표준 라인 매핑 룰 한계</b>: 현재 ko_label 키워드 매칭 룰이 미래에셋 라벨에 over-fit. 다음 라인은 미래에셋만 잡혀 1/8로 나옴 — 다른 회사 라벨 표현 보강 필요:
    <ul>
      <li>위험조정 변동분, 과거서비스 변동, 발생사고요소 조정, 발생사고비용, 기타증감 — 모두 1/8</li>
      <li>금융손익(OCI) — 0/8 (키워드 매칭 실패) → entity 확장 element 패턴 매칭 추가 필요</li>
    </ul>
  </li>
  <li><b>BS 잔액 검증 미흡</b>: 현재 SUM 쿼리가 n_axes redundancy 로 부풀려진 값. 다음 단계에서 MIN(n_axes) row family 만 사용해 재산출 필요. (현재 표의 BS 잔액은 참고용)</li>
  <li><b>손보 5분류 misfit</b>: 손보는 사망/연금/저축 거의 0 — 생보용 룰과 분리 필요. 보강 룰(장기/자동차/일반) 적용해도 일부 미분류 (무배당상해·재물 등 세부 멤버) 잔존.</li>
  <li><b>회사간 라벨 표현 차이</b>: 같은 IFRS 개념도 회사마다 표현 다름 (예: "위험조정 변동분" vs "비금융위험에 대한 위험조정의 변동분") — 매핑 사전 누적이 다음 분기 효과 누적.</li>
</ul>

<h2>7. 향후 개선 방안</h2>
<ol>
  <li><b>매핑 사전 보강</b> (priority HIGH) — 표준 라인별 키워드를 미래에셋 외 다른 회사 라벨 표현까지 확장. 특히 OCI·위험조정·과거서비스. xbrl-taxonomy-mapper 에이전트로 자동화.</li>
  <li><b>n_axes 정규화</b> (priority HIGH) — 모든 fact 조회 SQL 에 <code>MIN(n_axes) row family</code> 필터 표준 적용. BS 잔액 검증 신뢰성 확보.</li>
  <li><b>BEL/RA/CSM view 우선 진행</b> — 8개사 전부 가용·표준 axis 라 가장 신뢰도 높음. 자사 vs 동업사 비교 1차 보고에 활용 권장.</li>
  <li><b>상품군 view 는 생/손 분리 진행</b> — 손보용 axis (장기/자동차/일반)는 별도 표준화. liability_items.yml 의 contract_type_axis 섹션 보강.</li>
  <li><b>예외테이블 운영</b> — REVIEW (1/8 등) 라인은 별도 exceptions 테이블 누적 → 다음 분기 매핑 효과 측정.</li>
  <li><b>비상장 회사 자료 확보</b> — KB라이프·교보·신한·흥국은 DART 적재본에 부재 → 별도 제공처(금감원 보험사 공시) 검토.</li>
</ol>

<div class="footer-note">
  <p><b>분석 근거 파일</b></p>
  <ol>
    <li><code>report/coverage_matrix.csv</code> — Step 1 작성여부 매트릭스 (14×4)</li>
    <li><code>report/feasibility_summary.csv</code> — Step 2 회사별 적합성 요약 (8개사)</li>
    <li><code>report/feasibility_details.json</code> — Step 2 회사별 상세 (TypesAxis 멤버·Components 멤버·표준 라인)</li>
    <li><code>report/line_crosstab.csv</code> — Step 3 라인 × 회사 매트릭스 (21×8)</li>
    <li><code>report/analytic_scope.json</code> — Step 3 view 별 추천 분석</li>
  </ol>

  <p><b>방법론 메모</b></p>
  <ol>
    <li>모든 fact는 <code>ConsolidatedAndSeparateFinancialStatementsAxis=SeparateMember</code> +
        <code>DisaggregationOfInsuranceContractsAxis=InsuranceContractsIssuedMember</code> 필터 (별도 발행보험).</li>
    <li>표준 라인은 IFRS17 §103/§104 disclosure 항목 기준 21개로 정의.</li>
    <li>회사 매핑은 ko_label 키워드 매칭 — 미래에셋 라벨에 우선 최적화됨 (한계 §6 참조).</li>
    <li>이 보고서는 <b>자료 가용성 진단</b>이며 실제 수치 비교는 다음 단계(파이프라인 stage 5+) 에서 진행.</li>
  </ol>
</div>

</body>
</html>
"""

out = R / "feasibility_report.html"
out.write_text(html, encoding="utf-8")
print(f"wrote {out} ({len(html):,} bytes)")
