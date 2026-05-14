"""미래에셋 21-1 v2 — 상품군별 LRC/LIC 분해 차이 공시.

매핑 원칙:
1. 각 (상품군, 라인)은 하나의 값만 가진다. LRC 또는 LIC 컬럼 중 하나에 자연 귀속.
2. 잔액(open/close)과 손실부담계약 손실(환입), 발생사고요소 조정만 LRC·LIC 양쪽 보고.
3. 값은 (cons, disagg, types) 만 axis로 지정 (lrclic 차원 없는 broad 버전) → n_axes 최소화로
   double-counting 회피. 잔액·손실부담은 lrclic 포함.
4. 추출: 별도·발행·FY2025 (period_start=2025-01-01, period_end=2025-12-31, instant=2024-12-31|2025-12-31).
"""
from __future__ import annotations
import duckdb, re
from pathlib import Path

CIK = "00112332"
ROLE = "dart_2024-06-30_role-DI817100"

LRC_LIC_AXIS = "ifrs-full_InsuranceContractsByRemainingCoverageAndIncurredClaimsAxis"
TYPES_AXIS = "ifrs-full_TypesOfContractsAxis"
CONS_AXIS = "ifrs-full_ConsolidatedAndSeparateFinancialStatementsAxis"
DISAGG_AXIS = "ifrs-full_DisaggregationOfInsuranceContractsAxis"
SEP = "ifrs-full_SeparateMember"
ISSUED = "ifrs-full_InsuranceContractsIssuedMember"

LRC_EXCL = "ifrs-full_NetLiabilitiesOrAssetsForRemainingCoverageExcludingLossComponentMember"
LC = "ifrs-full_LossComponentMember"
LIC = "ifrs-full_LiabilitiesForIncurredClaimsMember"

PRODUCT_GROUPS = [
    ("death",   "사망", "dart_LifeInsuranceMember"),
    ("health",  "건강", "dart_HealthInsuranceMember"),
    ("pension", "연금", "entity00112332_PensionInsuranceOfInsuranceContractsMemberOfIDeathTableOfMember"),
    ("savings", "저축", "entity00112332_SavingsInsuranceOfInsuranceContractsMemberOfIDeathTableOfMember"),
    ("other",   "기타", "dart_OtherInsuranceMember"),
]

# 배당여부별 (Table 1) — 보험수익·투자요소는 여기에만 보고됨
DIVIDEND_MEMBERS = [
    "entity00112332_DividendContractOfTypesOfContractsMemberOfDisclosureOfNatureAndExtentOfRisksThatAriseFromContractsWithinScopeOfIFRS17TableOfMember",
    "entity00112332_ContractsOtherThanDividendsOfTypesOfContractsMemberOfDisclosureOfNatureAndExtentOfRisksThatAriseFromContractsWithinScopeOfIFRS17TableOfMember",
]

# 라인 정의: (key, label_match, period_type, col)
#   label_match: ko_label로 element 자동 탐색할 검색어 (정확 일치 우선, 없으면 LIKE)
#   col: 'LRC' | 'LIC' | 'BAL' (잔액: 자동 분해) | 'SPLIT' (-LRC, +LIC 분해)
LINES = [
    ("open",   "기초 잔액 (2024-12-31)",           "__balance__", "instant_open", "BAL", "balance"),
    ("revenue",     "보험수익",                   "총 보험수익",                      "duration", "LRC", ""),
    ("init_recog",  "신계약 인식 효과",            "해당 기간에 처음 인식한 계약의 영향",   "duration", "LRC", ""),
    ("csm_adjust",  "CSM 조정하는 추정치 변동",    "보험계약마진을 조정하는 추정치",       "duration", "LRC", ""),
    ("csm_not_adj", "CSM 미조정 추정치 변동",      "보험계약마진을 조정하지 않는 추정치",   "duration", "LRC", ""),
    ("ra_change",   "위험조정 변동분 (비금융위험)",  "위험조정 변동분",                  "duration", "LRC", ""),
    ("experience",  "경험조정",                   "경험조정",                         "duration", "LRC", ""),
    ("past_service","과거 서비스 관련 변동",        "과거서비스와 관련된 변동분",         "duration", "LIC", ""),
    ("onerous",     "손실부담계약 관련 손실(환입)",  "손실부담계약 관련 손실",            "duration", "SPLIT", ""),
    ("lic_adjust",  "발생사고요소의 조정",          "발생사고요소의 조정",                "duration", "LIC", ""),
    ("incurred",    "발생한 보험금·서비스비용",     "발생한 보험금 및 기타 보험서비스비용", "duration", "LIC", ""),
    ("premium",     "수취 보험료",                "수취한 보험료",                    "duration", "LRC", ""),
    ("claims_paid", "지급 보험금·서비스비용",       "지급한 보험금",                    "duration", "LIC", ""),
    ("acq_cf",      "보험취득 현금흐름 (지급)",    "보험취득현금흐름 지급",              "duration", "LRC", ""),
    ("acq_amort",   "보험취득 현금흐름 (상각)",    "보험취득현금흐름 상각",              "duration", "LRC", ""),
    ("invest_comp", "투자요소 및 보험료환급",       "투자요소",                        "duration", "LIC", ""),
    ("fin_pl",      "당기손익인식 보험금융손익",     "당기손익인식 보험금융손익",          "duration", "LRC", ""),
    ("fin_oci",     "기타포괄손익인식 보험금융손익 (OCI)", "기타포괄손익",                "duration", "LRC", ""),
    ("other_chg",   "기타 증감",                  "기타증감",                        "duration", "LRC", ""),
    ("close",  "기말 잔액 (2025-12-31)",           "__balance__", "instant_close", "BAL", "balance"),
]


def _period_filter_sql(period_type: str, alias: str = "p") -> tuple[str, list]:
    if period_type == "instant_open":
        return f"{alias}.PERIOD_INSTANT = ?", ["2024-12-31"]
    if period_type == "instant_close":
        return f"{alias}.PERIOD_INSTANT = ?", ["2025-12-31"]
    return f"{alias}.PERIOD_START_DATE = ? AND {alias}.PERIOD_END_DATE = ?", ["2025-01-01", "2025-12-31"]


def find_element_by_label(con, ko_label_keyword: str) -> list[str]:
    """ko_label 키워드로 DI817100 role 에서 사용된 element_id 들 반환 (n_facts DESC)."""
    sql = """
    SELECT v.ELEMENT_ID,
           MAX(CASE WHEN l.LANG='ko' THEN l.LABEL END) AS lbl,
           COUNT(*) AS n
    FROM val_insurers v
    JOIN pre_insurers p ON p.CIK=v.CIK AND p.ELEMENT_ID=v.ELEMENT_ID
    LEFT JOIN lab_insurers l ON l.CIK=v.CIK AND l.ELMT_ID=v.ELEMENT_ID
    WHERE v.CIK=? AND p.ROLE_ID=? AND v.amount_krw IS NOT NULL
    GROUP BY v.ELEMENT_ID
    HAVING lbl LIKE ?
    ORDER BY n DESC
    """
    return [r[0] for r in con.execute(sql, [CIK, ROLE, f"%{ko_label_keyword}%"]).fetchall()]


def _find_entity_element(con, ko_keyword: str, period_type: str) -> str | None:
    """미래에셋 OCI 금융손익 같이 entity 확장 element 자동 탐색."""
    period_sql, params = _period_filter_sql(period_type, "c")
    sql = f"""
    SELECT v.ELEMENT_ID, COUNT(*) AS n
    FROM val_insurers v
    LEFT JOIN lab_insurers l ON l.CIK=v.CIK AND l.ELMT_ID=v.ELEMENT_ID AND l.LANG='ko'
    WHERE v.CIK = ? AND v.amount_krw IS NOT NULL
      AND l.LABEL LIKE ?
      AND EXISTS (SELECT 1 FROM cntxt_insurers c
        WHERE c.CIK=v.CIK AND c.REPORT_DATE=v.REPORT_DATE AND c.CONTEXT_ID=v.CONTEXT_ID
          AND {period_sql})
    GROUP BY v.ELEMENT_ID ORDER BY n DESC LIMIT 5
    """
    res = con.execute(sql, [CIK, f"%{ko_keyword}%"] + params).fetchall()
    return res[0][0] if res else None


def fetch_total(con, element_id: str, types_member: str, period_type: str) -> float | None:
    """LRC/LIC 차원 없는 broad 컨텍스트에서 (별도·발행·types·element) 값 SUM.

    n_axes 최소값 row family만 사용해 다단계 redundancy 회피.
    """
    period_sql, period_params = _period_filter_sql(period_type)
    sql = f"""
    WITH ax_cnt AS (
      SELECT CIK, REPORT_DATE, CONTEXT_ID, COUNT(*) AS n_axes
      FROM cntxt_insurers
      WHERE CIK = ? AND REPORT_DATE = ?
      GROUP BY CIK, REPORT_DATE, CONTEXT_ID
    ),
    candidate AS (
      SELECT v.amount_krw, ax.n_axes
      FROM val_insurers v
      JOIN ax_cnt ax ON ax.CIK=v.CIK AND ax.REPORT_DATE=v.REPORT_DATE AND ax.CONTEXT_ID=v.CONTEXT_ID
      WHERE v.CIK = ? AND v.ELEMENT_ID = ? AND v.amount_krw IS NOT NULL
        AND EXISTS (SELECT 1 FROM cntxt_insurers cs
          WHERE cs.CIK=v.CIK AND cs.REPORT_DATE=v.REPORT_DATE AND cs.CONTEXT_ID=v.CONTEXT_ID
            AND cs.AXIS_ELEMENT_ID='{CONS_AXIS}' AND cs.MEMBER_ELEMENT_ID='{SEP}')
        AND EXISTS (SELECT 1 FROM cntxt_insurers cd
          WHERE cd.CIK=v.CIK AND cd.REPORT_DATE=v.REPORT_DATE AND cd.CONTEXT_ID=v.CONTEXT_ID
            AND cd.AXIS_ELEMENT_ID='{DISAGG_AXIS}' AND cd.MEMBER_ELEMENT_ID='{ISSUED}')
        AND EXISTS (SELECT 1 FROM cntxt_insurers ct
          WHERE ct.CIK=v.CIK AND ct.REPORT_DATE=v.REPORT_DATE AND ct.CONTEXT_ID=v.CONTEXT_ID
            AND ct.AXIS_ELEMENT_ID='{TYPES_AXIS}' AND ct.MEMBER_ELEMENT_ID=?)
        AND NOT EXISTS (SELECT 1 FROM cntxt_insurers cl
          WHERE cl.CIK=v.CIK AND cl.REPORT_DATE=v.REPORT_DATE AND cl.CONTEXT_ID=v.CONTEXT_ID
            AND cl.AXIS_ELEMENT_ID='{LRC_LIC_AXIS}')
        AND EXISTS (SELECT 1 FROM cntxt_insurers p
          WHERE p.CIK=v.CIK AND p.REPORT_DATE=v.REPORT_DATE AND p.CONTEXT_ID=v.CONTEXT_ID
            AND {period_sql})
    ),
    min_axes AS (SELECT MIN(n_axes) AS m FROM candidate)
    SELECT SUM(c.amount_krw)
    FROM candidate c, min_axes m
    WHERE c.n_axes = m.m
    """
    params = [CIK, "20251231", CIK, element_id, types_member] + period_params
    val = con.execute(sql, params).fetchone()[0]
    return float(val) if val is not None else None


def fetch_lrclic(con, element_id: str, types_member: str, lrclic_member: str, period_type: str) -> float | None:
    """LRC/LIC 차원 포함 — 잔액·손실부담계약·발생사고요소 조정 전용. min n_axes 적용."""
    period_sql, period_params = _period_filter_sql(period_type)
    sql = f"""
    WITH ax_cnt AS (
      SELECT CIK, REPORT_DATE, CONTEXT_ID, COUNT(*) AS n_axes
      FROM cntxt_insurers WHERE CIK = ? AND REPORT_DATE = ?
      GROUP BY CIK, REPORT_DATE, CONTEXT_ID
    ),
    candidate AS (
      SELECT v.amount_krw, ax.n_axes
      FROM val_insurers v
      JOIN ax_cnt ax ON ax.CIK=v.CIK AND ax.REPORT_DATE=v.REPORT_DATE AND ax.CONTEXT_ID=v.CONTEXT_ID
      WHERE v.CIK = ? AND v.ELEMENT_ID = ? AND v.amount_krw IS NOT NULL
        AND EXISTS (SELECT 1 FROM cntxt_insurers cs
          WHERE cs.CIK=v.CIK AND cs.REPORT_DATE=v.REPORT_DATE AND cs.CONTEXT_ID=v.CONTEXT_ID
            AND cs.AXIS_ELEMENT_ID='{CONS_AXIS}' AND cs.MEMBER_ELEMENT_ID='{SEP}')
        AND EXISTS (SELECT 1 FROM cntxt_insurers cd
          WHERE cd.CIK=v.CIK AND cd.REPORT_DATE=v.REPORT_DATE AND cd.CONTEXT_ID=v.CONTEXT_ID
            AND cd.AXIS_ELEMENT_ID='{DISAGG_AXIS}' AND cd.MEMBER_ELEMENT_ID='{ISSUED}')
        AND EXISTS (SELECT 1 FROM cntxt_insurers ct
          WHERE ct.CIK=v.CIK AND ct.REPORT_DATE=v.REPORT_DATE AND ct.CONTEXT_ID=v.CONTEXT_ID
            AND ct.AXIS_ELEMENT_ID='{TYPES_AXIS}' AND ct.MEMBER_ELEMENT_ID=?)
        AND EXISTS (SELECT 1 FROM cntxt_insurers cl
          WHERE cl.CIK=v.CIK AND cl.REPORT_DATE=v.REPORT_DATE AND cl.CONTEXT_ID=v.CONTEXT_ID
            AND cl.AXIS_ELEMENT_ID='{LRC_LIC_AXIS}' AND cl.MEMBER_ELEMENT_ID=?)
        AND EXISTS (SELECT 1 FROM cntxt_insurers p
          WHERE p.CIK=v.CIK AND p.REPORT_DATE=v.REPORT_DATE AND p.CONTEXT_ID=v.CONTEXT_ID
            AND {period_sql})
    ),
    min_axes AS (SELECT MIN(n_axes) AS m FROM candidate)
    SELECT SUM(c.amount_krw)
    FROM candidate c, min_axes m
    WHERE c.n_axes = m.m
    """
    params = [CIK, "20251231", CIK, element_id, types_member, lrclic_member] + period_params
    val = con.execute(sql, params).fetchone()[0]
    return float(val) if val is not None else None


# 잔액 element들
BALANCE_ELEMS = [
    "ifrs-full_InsuranceContractsThatAreAssets",
    "ifrs-full_InsuranceContractsThatAreLiabilities",
]


def fetch_balance(con, types_member: str, lrclic_member: str, period_type: str) -> float | None:
    """잔액 = Assets + Liabilities 부호합 (with LRC/LIC dim)."""
    total = None
    for e in BALANCE_ELEMS:
        v = fetch_lrclic(con, e, types_member, lrclic_member, period_type)
        if v is not None:
            total = (total or 0) + v
    return total


def fetch_balance_lrc(con, types_member: str, period_type: str) -> float | None:
    """잔액 LRC = LRC_excl + LossComponent."""
    a = fetch_balance(con, types_member, LRC_EXCL, period_type)
    b = fetch_balance(con, types_member, LC, period_type)
    if a is None and b is None: return None
    return (a or 0) + (b or 0)


def fetch_balance_lic(con, types_member: str, period_type: str) -> float | None:
    return fetch_balance(con, types_member, LIC, period_type)


def fetch_split(con, element_id: str, types_member: str, period_type: str) -> tuple[float | None, float | None]:
    """SPLIT: 손실부담계약 손실 — LRC(=excl+LC) 와 LIC 두 값 반환."""
    excl = fetch_lrclic(con, element_id, types_member, LRC_EXCL, period_type)
    lc = fetch_lrclic(con, element_id, types_member, LC, period_type)
    lic = fetch_lrclic(con, element_id, types_member, LIC, period_type)
    lrc = None
    if excl is not None or lc is not None:
        lrc = (excl or 0) + (lc or 0)
    return lrc, lic


def fmt(v: float | None) -> str:
    if v is None: return "&mdash;"
    in_억 = v / 1e8
    if abs(in_억) < 0.5: return "&nbsp;"
    return f"{in_억:+,.0f}".replace("-", "&minus;")


def main():
    con = duckdb.connect("data/db/benchmark.duckdb", read_only=True)

    # 라인별 element 매핑 — ko_label 으로 자동 탐색
    line_elements: dict[str, list[str]] = {}
    for line_key, label, lbl_match, ptype, col, css in LINES:
        if lbl_match == "__balance__":
            line_elements[line_key] = BALANCE_ELEMS
            continue
        eids = find_element_by_label(con, lbl_match)
        # OCI: pre.xml의 canonical entity element 한 개만 사용
        if not eids and line_key == "fin_oci":
            sql = """
            SELECT DISTINCT v.ELEMENT_ID, COUNT(*) AS n
            FROM val_insurers v JOIN pre_insurers p USING (CIK, ELEMENT_ID)
            WHERE v.CIK=? AND p.ROLE_ID=? AND v.amount_krw IS NOT NULL
              AND v.ELEMENT_ID LIKE 'entity00112332_InsuranceFinanceIncomeExpensesFromInsuranceContractsIssuedRecognisedInOtherCompe%InsuranceContractsLiabilityAssetOfDisclosure%'
            GROUP BY v.ELEMENT_ID ORDER BY n DESC LIMIT 1
            """
            eids = [r[0] for r in con.execute(sql, [CIK, ROLE]).fetchall()]
        line_elements[line_key] = eids
        print(f"  {label:40s} → {len(eids)} elements: {(eids[:1] or ['<none>'])}")

    # row_values[line_key] = {col_key: value}
    rows = []
    for line_key, label, lbl_match, ptype, col, css in LINES:
        eids = line_elements[line_key]

        def _fetch_for_member(pmember, fetch_fn):
            """element들에 대해 fetch → 우선 no-LRC/LIC, 없으면 LRC/LIC sum."""
            results = [fetch_fn(con, eid, pmember, ptype) for eid in eids]
            results = [r for r in results if r is not None]
            if results:
                return sum(results)
            # Fallback: LRC/LIC 차원만 있는 element는 LRC+LIC 합산
            fallback = 0.0
            found = False
            for eid in eids:
                for m in (LRC_EXCL, LC, LIC):
                    v = fetch_lrclic(con, eid, pmember, m, ptype)
                    if v is not None:
                        fallback += v
                        found = True
            return fallback if found else None

        cells = {}
        for pkey, plabel, pmember in PRODUCT_GROUPS:
            if col == "BAL":
                lrc = fetch_balance_lrc(con, pmember, ptype)
                lic = fetch_balance_lic(con, pmember, ptype)
            elif col == "SPLIT":
                # SPLIT: 손실부담계약 — 각 element별로 LRC/LIC 분해 후 합산
                lrc_total, lic_total = None, None
                for eid in eids:
                    l1, l2 = fetch_split(con, eid, pmember, ptype)
                    if l1 is not None: lrc_total = (lrc_total or 0) + l1
                    if l2 is not None: lic_total = (lic_total or 0) + l2
                lrc, lic = lrc_total, lic_total
            elif col == "LRC":
                lrc = _fetch_for_member(pmember, fetch_total)
                lic = None
            elif col == "LIC":
                lrc = None
                lic = _fetch_for_member(pmember, fetch_total)
            else:
                lrc, lic = None, None
            cells[f"{pkey}_LRC"] = lrc
            cells[f"{pkey}_LIC"] = lic

        # 합계: 5상품군 산술합
        def _sum_col(suffix):
            vs = [cells[f"{p[0]}_{suffix}"] for p in PRODUCT_GROUPS if cells[f"{p[0]}_{suffix}"] is not None]
            return sum(vs) if vs else None
        cells["total_LRC"] = _sum_col("LRC")
        cells["total_LIC"] = _sum_col("LIC")

        # Fallback: 5상품군 cell이 전부 비어있으면 (예: 보험수익·투자요소)
        # 배당여부별(Dividend + NonDividend) sum 으로 합계만 채움
        product_filled = any(cells[f"{p[0]}_LRC"] is not None or cells[f"{p[0]}_LIC"] is not None
                              for p in PRODUCT_GROUPS)
        if not product_filled and col in ("LRC", "LIC") and eids:
            div_lrc, div_lic = None, None
            for dm in DIVIDEND_MEMBERS:
                if col == "LRC":
                    for eid in eids:
                        v = fetch_total(con, eid, dm, ptype)
                        if v is None:
                            # fallback to LRC/LIC sum
                            for m in (LRC_EXCL, LC):
                                vv = fetch_lrclic(con, eid, dm, m, ptype)
                                if vv is not None: v = (v or 0) + vv
                        if v is not None: div_lrc = (div_lrc or 0) + v
                else:
                    for eid in eids:
                        v = fetch_total(con, eid, dm, ptype)
                        if v is None:
                            v = fetch_lrclic(con, eid, dm, LIC, ptype)
                        if v is not None: div_lic = (div_lic or 0) + v
            cells["total_LRC"] = div_lrc
            cells["total_LIC"] = div_lic
            cells["fallback"] = "배당여부별합산"

        cells["grand"] = (cells["total_LRC"] or 0) + (cells["total_LIC"] or 0) \
            if cells["total_LRC"] is not None or cells["total_LIC"] is not None else None
        rows.append((line_key, label, css, cells))

    # build HTML rows
    COLS = []
    for pkey, _, _ in PRODUCT_GROUPS:
        COLS.extend([f"{pkey}_LRC", f"{pkey}_LIC"])
    COLS.extend(["total_LRC", "total_LIC", "grand"])

    rows_html = []
    for line_key, label, css, cells in rows:
        tr_class = f' class="{css}"' if css else ""
        td_class = "label section" if css == "balance" else "label"
        if css == "balance":
            td_class = "label"
        # 들여쓰기 처리 (잔액 외 모든 라인)
        tds = [f'<td class="{td_class}">{label}</td>']
        for col in COLS:
            v = cells.get(col)
            tot_class = " total-col" if col.startswith("total_") or col == "grand" else ""
            tds.append(f'<td class="num{tot_class}">{fmt(v)}</td>')
        rows_html.append(f"<tr{tr_class}>{''.join(tds)}</tr>")

    template = Path("report/21-1_보험계약부채변동_LRC_LIC_template.html").read_text(encoding="utf-8")
    new_tbody = "\n".join(rows_html)
    out = re.sub(r"<tbody>.*?</tbody>", f"<tbody>\n{new_tbody}\n</tbody>", template, count=1, flags=re.DOTALL)
    out = out.replace("미래에셋생명 표준 양식)", "값 채움 v2)")
    out = out.replace("— LRC/LIC × 상품군</h1>", "— LRC/LIC × 상품군 (미래에셋생명 2025, v2)</h1>")
    out = out.replace("(단위: 원)", "(단위: 억원 — 5천만 미만 빈칸, 부호: 부채 증가 +, 감소 −)")

    Path("report/21-1_보험계약부채변동_LRC_LIC_미래에셋_2025_v2.html").write_text(out, encoding="utf-8")
    print("\nwrote report/21-1_보험계약부채변동_LRC_LIC_미래에셋_2025_v2.html\n")

    print("=== 합계열 ===")
    for line_key, label, css, cells in rows:
        lab = label[:36]
        def f(v): return f"{v/1e8:+10,.0f}억" if v is not None else "         —"
        print(f"  {lab:38s} LRC={f(cells['total_LRC'])}  LIC={f(cells['total_LIC'])}  합={f(cells['grand'])}")

    # 사망 검증
    print("\n=== 사망 검증 ===")
    for line_key, label, css, cells in rows:
        lab = label[:36]
        def f(v): return f"{v/1e8:+10,.0f}억" if v is not None else "         —"
        print(f"  {lab:38s} LRC={f(cells['death_LRC'])}  LIC={f(cells['death_LIC'])}")


if __name__ == "__main__":
    main()
