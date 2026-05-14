"""종합보고서 v3 — 영문 element name 기준 유기적 매핑.

핵심 변경:
- 매핑 키: 영문 element name substring (자사 단위 한국어 라벨 X)
- 분해 깊이 자동 흡수: 풀린 회사 = axis 합산, 묶인 회사 = 그대로 → 같은 수준 비교
- 각 표준 패턴에 dart_/ifrs-full_ 표준 + entity 확장 모두 매핑

패턴 (9개, 자사 11개 단위에서 추출한 영문 본질):
  P1 DisclosureOfReconciliationOfChangesInInsuranceContractsIssuedByRemainingCoverageAndIncurredClaims (LRC/LIC 차이조정)
  P2 DisclosureOfReconciliationOfChangesInInsuranceContractsIssuedByComponents (구성요소 차이조정)
  P3 ChangesInInsuranceLiabilitiesBasedOnActuarialAssumptions (계리적 가정 변동)
  P4 ExpectedRevenueRecognitionAmountByPeriodOfContractualServiceMargin (CSM 기간별)
  P5 InsuranceLiabilitiesByAccountingModelAndPortfolio (회계모형·포트폴리오)
  P6 InvestmentServiceProfitAndInsuranceRelatedFinancialIncomeAndLoss (투자수익·보험금융)
  P7 InsuranceRevenue (보험수익 분해 — 일반/RA변동/CSM상각 등)
  P8 OffsettingEffectOfDerivativesOnFinancialRiskOfInsuranceContractsWithDirectParticipation (직접참가 파생)
  P9 UnderlyingItemsForInsuranceContractsWithDirectParticipationFeatures (직접참가 기초항목)
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from textwrap import dedent

import duckdb

from peer_benchmarking.domain import peer_groups

SELF_CIK = "00112332"
ROLE = "dart_2024-06-30_role-DI817100"
CIKS = ("00112332", "00126256", "00113058", "00117267",
        "00139214", "00164973", "00159102", "00135917", "00103176")

# 표준 영문 element name 패턴 — 자사 11개 단위에서 추출한 본질
PATTERNS = [
    ("P1", "LRC/LIC 차이조정",
     "DisclosureOfReconciliationOfChangesInInsuranceContractsIssuedByRemainingCoverageAndIncurredClaims"),
    ("P2", "구성요소 차이조정",
     "DisclosureOfReconciliationOfChangesInInsuranceContractsIssuedByComponents"),
    ("P3", "계리적 가정 변동",
     "ChangesInInsuranceLiabilitiesBasedOnActuarialAssumptions"),
    ("P4", "CSM 기간별 기대수익",
     "ExpectedRevenueRecognitionAmountByPeriodOfContractualServiceMargin"),
    ("P5", "회계모형·포트폴리오",
     "InsuranceLiabilitiesByAccountingModelAndPortfolio"),
    ("P6", "투자서비스수익·보험금융",
     "InvestmentServiceProfitAndInsuranceRelatedFinancialIncomeAndLoss"),
    ("P7", "보험수익 분해",
     "InsuranceRevenue"),
    ("P8", "직접참가 파생 상쇄",
     "OffsettingEffectOfDerivativesOnFinancialRiskOfInsuranceContractsWithDirectParticipation"),
    ("P9", "직접참가 기초항목",
     "UnderlyingItemsForInsuranceContractsWithDirectParticipationFeatures"),
]


def fetch_pattern_per_cik(con, cik: str, pat: str) -> dict:
    """한 회사의 한 패턴에 매칭되는 element 분포 + 값 보유."""
    rows = con.execute("""
    SELECT DISTINCT p.ELEMENT_ID, em.ABSTRACT, em.SUBSTITUTION_GROUP
    FROM pre_insurers p
    JOIN elmt_raw em ON em.ELEMENT_ID = p.ELEMENT_ID
    WHERE p.CIK=? AND p.ROLE_ID=? AND p.ELEMENT_ID LIKE ?
    """, [cik, ROLE, f"%{pat}%"]).fetchall()

    if not rows:
        return {"n_elem": 0, "n_lineitem": 0, "n_with_val": 0,
                "max_amount": None, "elems": [], "std_count": 0, "ent_count": 0}

    elems_info = []
    n_li = 0
    n_val = 0
    max_amt = None
    std_n = 0
    ent_n = 0

    for elem, abs_, sg in rows:
        is_li = (str(abs_).lower() != "true" and sg == "xbrli:item")
        is_entity = elem.startswith("entity")
        std_n += (0 if is_entity else 1)
        ent_n += (1 if is_entity else 0)
        # value summary
        vrow = con.execute("""
        SELECT COUNT(DISTINCT CONTEXT_ID), MAX(amount_krw)
        FROM val_insurers WHERE CIK=? AND ELEMENT_ID=? AND amount_krw IS NOT NULL
        """, [cik, elem]).fetchone()
        nctx, vmax = vrow
        if is_li:
            n_li += 1
            if nctx and nctx > 0:
                n_val += 1
                if vmax is not None and (max_amt is None or vmax > max_amt):
                    max_amt = vmax
        elems_info.append({"elem": elem, "is_lineitem": is_li,
                           "is_entity": is_entity, "n_ctx": nctx, "max_amt": vmax})
    return {"n_elem": len(rows), "n_lineitem": n_li, "n_with_val": n_val,
            "max_amount": max_amt, "elems": elems_info,
            "std_count": std_n, "ent_count": ent_n}


def total_amount_for_pattern(con, cik: str, pat: str) -> tuple[int, float | None]:
    """패턴 내 모든 element의 LRC+LIC 또는 BEL+RA+CSM 합산 (분해 깊이 흡수).

    cons/sep axis (Separate) + 패턴 element + ABSTRACT=false 조합의 amount_krw 합 — 단,
    중복 카운트 방지 위해 axis-min context만.
    """
    sql = """
    WITH ax_cnt AS (
      SELECT CIK, REPORT_DATE, CONTEXT_ID, COUNT(*) AS n_axes
      FROM cntxt_insurers WHERE CIK=? AND REPORT_DATE='20251231'
      GROUP BY CIK, REPORT_DATE, CONTEXT_ID
    )
    SELECT COUNT(DISTINCT v.ELEMENT_ID) AS n_li_val,
           SUM(v.amount_krw) AS total_amt
    FROM val_insurers v
    JOIN ax_cnt a USING (CIK, REPORT_DATE, CONTEXT_ID)
    JOIN elmt_raw em ON em.ELEMENT_ID = v.ELEMENT_ID
    WHERE v.CIK=?
      AND v.ELEMENT_ID LIKE ?
      AND v.amount_krw IS NOT NULL
      AND em.ABSTRACT != 'true'
      AND em.SUBSTITUTION_GROUP='xbrli:item'
      AND EXISTS (
        SELECT 1 FROM cntxt_insurers c
        WHERE c.CIK=v.CIK AND c.REPORT_DATE=v.REPORT_DATE AND c.CONTEXT_ID=v.CONTEXT_ID
          AND c.AXIS_ELEMENT_ID='ifrs-full_ConsolidatedAndSeparateFinancialStatementsAxis'
          AND c.MEMBER_ELEMENT_ID='ifrs-full_SeparateMember'
      )
      AND a.n_axes = (
        SELECT MIN(a2.n_axes) FROM val_insurers v2
        JOIN ax_cnt a2 USING (CIK, REPORT_DATE, CONTEXT_ID)
        WHERE v2.CIK=v.CIK AND v2.ELEMENT_ID=v.ELEMENT_ID AND v2.amount_krw IS NOT NULL
          AND EXISTS (
            SELECT 1 FROM cntxt_insurers c2
            WHERE c2.CIK=v2.CIK AND c2.CONTEXT_ID=v2.CONTEXT_ID
              AND c2.AXIS_ELEMENT_ID='ifrs-full_ConsolidatedAndSeparateFinancialStatementsAxis'
              AND c2.MEMBER_ELEMENT_ID='ifrs-full_SeparateMember'
          )
      )
    """
    r = con.execute(sql, [cik, cik, f"%{pat}%"]).fetchone()
    return (r[0] or 0, r[1])


def extract_css(base_html_path: Path) -> str:
    text = base_html_path.read_text(encoding="utf-8")
    m = re.search(r"<style.*?</style>", text, re.DOTALL)
    return m.group() if m else ""


def main() -> int:
    con = duckdb.connect("data/db/benchmark.duckdb", read_only=True)
    name_map = peer_groups.load_companies()

    # 1. 패턴 × 회사 매핑
    matrix = {}  # matrix[pat_id][cik] = {n_elem, n_lineitem, ...}
    for pat_id, pat_ko, pat in PATTERNS:
        matrix[pat_id] = {}
        for cik in CIKS:
            matrix[pat_id][cik] = fetch_pattern_per_cik(con, cik, pat)

    # 2. 합산 (분해 깊이 흡수) — axis-min context 합
    totals = {}  # totals[pat_id][cik] = (n_li_val, total_amt)
    for pat_id, pat_ko, pat in PATTERNS:
        totals[pat_id] = {}
        for cik in CIKS:
            totals[pat_id][cik] = total_amount_for_pattern(con, cik, pat)

    con.close()

    # 3. 통계
    total_cells = len(PATTERNS) * len(CIKS)
    have_pattern = sum(1 for p in matrix for c in matrix[p].values() if c["n_elem"] > 0)
    have_value = sum(1 for p in matrix for c in matrix[p].values() if c["n_with_val"] > 0)

    css = extract_css(Path("report/종합보고서_FY2025.html"))
    today = date.today().isoformat()

    # ─── §1 결론 카드 ───
    s1 = dedent(f"""
    <h2 id="sec-1-결론">1. 검토 결론 (영문 element name 기준 유기적 매핑)</h2>
    <div class="cards">
      <div class="card info">
        <div class="label">표준 영문 패턴</div>
        <div class="num">{len(PATTERNS)}</div>
        <div class="sub">자사 11개 단위에서 추출한 본질</div>
      </div>
      <div class="card pass">
        <div class="label">패턴 보유 (n_elem &gt; 0)</div>
        <div class="num">{have_pattern} / {total_cells}</div>
        <div class="sub">{have_pattern/total_cells*100:.1f}% — element 발견</div>
      </div>
      <div class="card warn">
        <div class="label">값 보유 (n_with_val &gt; 0)</div>
        <div class="num">{have_value} / {total_cells}</div>
        <div class="sub">{have_value/total_cells*100:.1f}% — 실제 수치 보고</div>
      </div>
      <div class="card review">
        <div class="label">미공시</div>
        <div class="num">{total_cells - have_pattern} / {total_cells}</div>
        <div class="sub">{(total_cells-have_pattern)/total_cells*100:.1f}% — 패턴 자체 없음</div>
      </div>
    </div>
    <div class="conclusion">
      <h4>핵심 결론 (이전 v2 매핑보다 정확)</h4>
      <ul>
        <li>매핑 키를 자사 단위 한국어 라벨 → <b>영문 element name 본질 substring</b>으로 변경.
            회사마다 풀어서/묶어서 보고하는 차이를 LIKE 매칭으로 흡수.</li>
        <li><b>P1 LRC/LIC 차이조정 + P2 구성요소 차이조정</b>은 7-8/9개사 보유 — 표준 비교 가능.</li>
        <li><b>P3 계리적가정·P4 CSM 만기·P5 회계모형·P6 투자수익·P8/P9 직접참가</b>는 자사 특화 entity 확장 단위.
            다른 회사는 같은 정보를 다른 패턴으로 보고했거나 미공시.</li>
        <li>금액 합산은 <b>axis-min context</b> 사용 — 회사가 풀어서 보고하면 분해 row 중 가장 집계 수준 높은
            것만 골라 double-count 방지. 회사 간 동일 수준 비교.</li>
      </ul>
    </div>
    """).strip()

    # ─── §2 패턴 × 회사 매트릭스 ───
    s2_th = "<th>패턴</th><th>영문 substring</th><th class='self'>미래에셋</th>" + \
            "".join(f'<th>{name_map[c].name_ko}</th>' for c in CIKS[1:])
    s2_rows = []
    for pat_id, pat_ko, pat in PATTERNS:
        cells_elem = [
            f'<td rowspan="3"><b>{pat_id}</b><br><span style="font-size:0.85em;color:#666">{pat_ko}</span></td>',
            '<td rowspan="3" style="font-size:0.75em;font-family:monospace">' + pat[:55] + '…</td>',
            '<td class="self" style="text-align:right">' +
                f'{matrix[pat_id][SELF_CIK]["n_elem"]}</td>',
        ]
        for cik in CIKS[1:]:
            n = matrix[pat_id][cik]["n_elem"]
            cls = "pass-cell" if n > 0 else "fail-cell"
            cells_elem.append(f'<td class="{cls}">{n}</td>')
        s2_rows.append('<tr>' + ''.join(cells_elem) + '</tr>')

        cells_li = ['<td>LineItem (값보유)</td>',
                    f'<td class="self" style="text-align:right">'
                    f'{matrix[pat_id][SELF_CIK]["n_with_val"]}</td>']
        for cik in CIKS[1:]:
            v = matrix[pat_id][cik]["n_with_val"]
            cls = "pass-cell" if v > 0 else "fail-cell"
            cells_li.append(f'<td class="{cls}">{v}</td>')
        s2_rows.append('<tr>' + ''.join(cells_li) + '</tr>')

        cells_amt = ['<td>합계 (조원, axis-min)</td>']
        for cik in CIKS:
            t = totals[pat_id][cik][1]
            if t is None:
                cells_amt.append('<td style="text-align:right;color:#aaa">—</td>')
            else:
                cls = "self" if cik == SELF_CIK else ""
                cells_amt.append(
                    f'<td class="{cls}" style="text-align:right">{t/1e12:,.2f}</td>'
                )
        s2_rows.append('<tr>' + ''.join(cells_amt) + '</tr>')

    s2 = dedent(f"""
    <h2 id="sec-2-매트릭스">2. 영문 패턴 × 9개사 매핑 매트릭스</h2>
    <p>각 패턴 (영문 element name substring) 별로 회사별 element 수 / 값보유 / axis-min 합계 조원.
    회사 간 분해 깊이 차이는 axis-min 합산으로 흡수.</p>
    <div class="table-wrap">
    <table>
      <thead><tr>{s2_th}</tr></thead>
      <tbody>{''.join(s2_rows)}</tbody>
    </table>
    </div>
    """).strip()

    # ─── §3 패턴별 상세 ───
    s3_sections = ['<h2 id="sec-3-상세">3. 패턴별 상세 — element 분포 + 값 합산</h2>']
    for pat_id, pat_ko, pat in PATTERNS:
        # 회사별 std vs entity 분포
        rows_html = []
        for cik in CIKS:
            d = matrix[pat_id][cik]
            t = totals[pat_id][cik]
            cls = "self" if cik == SELF_CIK else ""
            amt_str = f'{t[1]/1e12:,.2f}' if t[1] is not None else '—'
            rows_html.append(
                f'<tr class="{cls}"><td>{name_map[cik].name_ko}</td>'
                f'<td style="text-align:right">{d["n_elem"]}</td>'
                f'<td style="text-align:right">{d["n_lineitem"]}</td>'
                f'<td style="text-align:right">{d["n_with_val"]}</td>'
                f'<td style="text-align:right">{d["std_count"]}</td>'
                f'<td style="text-align:right">{d["ent_count"]}</td>'
                f'<td style="text-align:right">{amt_str}</td></tr>'
            )
        s3_sections.append(dedent(f"""
        <h3 id="sec-3-{pat_id}">{pat_id}. {pat_ko}</h3>
        <p style="font-family:monospace;font-size:0.8em;color:#555">패턴: <code>{pat}</code></p>
        <div class="table-wrap">
        <table>
          <thead><tr>
            <th>회사</th><th>총 element</th><th>LineItem</th><th>값 보유</th>
            <th>표준(dart/ifrs)</th><th>entity 확장</th><th>합계 (조)</th>
          </tr></thead>
          <tbody>{''.join(rows_html)}</tbody>
        </table>
        </div>
        """))
    s3 = "\n".join(s3_sections)

    # ─── §4 한계 ───
    s4 = dedent("""
    <h2 id="sec-4-한계">4. 한계 · 다음 단계</h2>
    <div class="conclusion warning">
      <h4>한계</h4>
      <ul>
        <li><b>합계 axis-min 합산</b>은 sub-table 안에 추가 axis가 있어도 가장 집계된 row만 골라 double-count 회피.
            다만 회사마다 axis 구성이 다르면 합계 의미가 다를 수 있음 — 핵심 패턴(P1, P2)은 표준 dart로 일관성 높음.</li>
        <li><b>자사 entity 확장 패턴 (P3·P5·P6·P8·P9)</b>은 자사 특화. 동업사 미공시·다른 패턴 사용 가능.</li>
        <li>P7 (보험수익)은 단순 substring 매칭이라 너무 많은 element가 잡힘 — 정밀화 필요.</li>
      </ul>
    </div>
    <div class="conclusion">
      <h4>다음 단계</h4>
      <ul>
        <li>P1·P2 핵심 패턴의 BEL/RA/CSM × LRC/LIC 분해 표 — 회사별 axis 합산하여 BS 매칭 검증.</li>
        <li>P7 보험수익은 (1) 총 보험수익 (2) CSM 상각·RA 변동분 세분으로 분리해 비교.</li>
        <li>P3 계리적가정은 §5.11 패턴 적용 (회사별 정확 search).</li>
      </ul>
    </div>
    """).strip()

    # ─── TOC ───
    toc = dedent("""
    <div class="toc-container">
      <div class="toc-toggle" onclick="document.getElementById('toc-list').classList.toggle('hidden')">📑 목차</div>
      <div id="toc-list" class="toc-list">
        <div class="toc-group">
          <h4 class="toc-group-title">개요</h4>
          <a class="toc-item" href="#sec-1-결론">1. 검토 결론</a>
          <a class="toc-item" href="#sec-2-매트릭스">2. 매핑 매트릭스</a>
        </div>
        <div class="toc-group">
          <h4 class="toc-group-title">패턴 상세 (9개)</h4>
    """)
    for pat_id, pat_ko, _ in PATTERNS:
        toc += f'      <a class="toc-item" href="#sec-3-{pat_id}">{pat_id}. {pat_ko}</a>\n'
    toc += dedent("""
        </div>
        <div class="toc-group">
          <h4 class="toc-group-title">결론·한계</h4>
          <a class="toc-item" href="#sec-4-한계">4. 한계·다음 단계</a>
        </div>
      </div>
    </div>
    """)

    html = dedent(f"""
    <!doctype html>
    <html lang='ko'><head><meta charset='utf-8'>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>종합보고서 v3 — DI817100 영문 element name 기준 유기적 매핑</title>
    {css}
    </head><body>
      <h1>📊 종합보고서 v3 — DI817100 영문 element 기준 유기적 매핑</h1>
      <div class="meta">
        <span>자사: 미래에셋생명 (CIK {SELF_CIK})</span>
        <span>동업사: 8개 IFRS17 풍부 KOSPI 상장</span>
        <span>기준: 별도(separate) · {today}</span>
        <span>규칙: no-inference + 분해 깊이 axis-min 흡수</span>
      </div>
      {toc}
      {s1}
      {s2}
      {s3}
      {s4}
      <div class="footer-note">
        build_report_v3.py · 영문 element name substring 기준 매핑 · 회사별 axis 깊이 차이 흡수
      </div>
    </body></html>
    """).strip()

    out = Path("report/종합보고서_v3_DI817100.html")
    out.write_text(html, encoding="utf-8")
    print(f"✓ wrote {out} ({out.stat().st_size / 1024:.1f} KB)")

    # CLI 요약
    print()
    print('=== 패턴 × 회사 매트릭스 (총 element 수) ===')
    print(f'  {"":18s} ', '  '.join(f'{name_map[c].name_ko[:5]:>6s}' for c in CIKS))
    for pat_id, pat_ko, _ in PATTERNS:
        print(f'  {pat_id} {pat_ko[:13]:14s} ', '  '.join(
            f'{matrix[pat_id][c]["n_elem"]:>6d}' for c in CIKS))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
