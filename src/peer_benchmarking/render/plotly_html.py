"""Plotly HTML report — 인터랙티브 차트 단일 HTML 파일.

이 layer는 analysis 모듈에서 받은 DataFrame을 차트로 변환만 함.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import duckdb
import pandas as pd
import plotly.graph_objects as go

from peer_benchmarking.analysis import cross_section, measurement_model, ratios
from peer_benchmarking.analysis.queries import QuerySpec
from peer_benchmarking.domain import peer_groups
from peer_benchmarking.render.formatters import to_trillion

# Colors
SELF_COLOR = "#F59E0B"      # amber
PEER_COLOR = "#3B82F6"      # blue
LIFE_COLOR = "#10B981"
NON_LIFE_COLOR = "#8B5CF6"
REINS_COLOR = "#EC4899"


def _bar_with_self_highlight(
    df: pd.DataFrame,
    title: str,
    value_unit: str = "조원",
    self_cik: str | None = None,
) -> go.Figure:
    """Sorted bar chart, self colored amber, others blue."""
    self_cik = self_cik or peer_groups.self_cik()
    if df.empty:
        fig = go.Figure()
        fig.update_layout(title=f"{title} (데이터 없음)")
        return fig

    sub = df.sort_values("amount_krw", ascending=False).reset_index(drop=True).copy()
    sub["val"] = to_trillion(sub["amount_krw"])
    colors = [SELF_COLOR if c == self_cik else PEER_COLOR for c in sub["cik"]]

    fig = go.Figure(
        go.Bar(
            x=sub["name_ko"],
            y=sub["val"],
            marker_color=colors,
            text=sub["val"].map(lambda v: f"{v:,.2f}"),
            textposition="outside",
            hovertemplate="%{x}: %{y:,.2f} " + value_unit + "<extra></extra>",
        )
    )
    fig.update_layout(
        title=title,
        yaxis_title=f"금액({value_unit})",
        xaxis_title=None,
        showlegend=False,
        template="plotly_white",
        height=400,
    )
    return fig


def _stacked_model_share(df: pd.DataFrame, self_cik: str | None = None) -> go.Figure:
    """PAA vs Non-PAA 100% stacked bar."""
    self_cik = self_cik or peer_groups.self_cik()
    if df.empty:
        return go.Figure().update_layout(title="회계모형 분포 (데이터 없음)")

    sub = df.sort_values("total", ascending=False).reset_index(drop=True).copy()
    sub["paa_pct"] = sub["paa_share"].fillna(0) * 100
    sub["nonpaa_pct"] = sub["nonpaa_share"].fillna(0) * 100
    name_marker = [
        f"<b>{n}</b> ★" if c == self_cik else n
        for n, c in zip(sub["name_ko"], sub["cik"], strict=True)
    ]

    fig = go.Figure([
        go.Bar(name="PAA", x=name_marker, y=sub["paa_pct"], marker_color="#F59E0B",
               hovertemplate="%{x}<br>PAA: %{y:.1f}%<extra></extra>"),
        go.Bar(name="Non-PAA (GMM+VFA)", x=name_marker, y=sub["nonpaa_pct"],
               marker_color="#3B82F6",
               hovertemplate="%{x}<br>Non-PAA: %{y:.1f}%<extra></extra>"),
    ])
    fig.update_layout(
        title="회계모형 분포: PAA vs Non-PAA (보험계약부채 기준 %)",
        barmode="stack",
        yaxis_title="비중 (%)",
        template="plotly_white",
        height=420,
    )
    return fig


def _peer_distribution_box(df: pd.DataFrame, title: str, self_cik: str | None = None) -> go.Figure:
    """Box plot of peer distribution with self overlaid as a marker."""
    self_cik = self_cik or peer_groups.self_cik()
    if df.empty:
        return go.Figure().update_layout(title=f"{title} (데이터 없음)")

    values = to_trillion(df["amount_krw"])
    fig = go.Figure()
    fig.add_trace(go.Box(
        y=values,
        name="Peer 분포",
        boxpoints="all",
        jitter=0.4,
        pointpos=0,
        marker=dict(color=PEER_COLOR, size=6),
        line=dict(color=PEER_COLOR),
        hovertext=df["name_ko"],
        hovertemplate="%{hovertext}: %{y:,.2f} 조원<extra></extra>",
    ))
    # Self marker
    self_row = df[df["cik"] == self_cik]
    if not self_row.empty:
        self_val = to_trillion(self_row["amount_krw"]).iloc[0]
        fig.add_trace(go.Scatter(
            x=["Peer 분포"], y=[self_val],
            mode="markers+text",
            marker=dict(color=SELF_COLOR, size=14, symbol="star"),
            text=[f"★ 미래에셋생명 {self_val:,.2f}조"],
            textposition="middle right",
            name="자사",
            hoverinfo="skip",
        ))
    fig.update_layout(
        title=title,
        yaxis_title="금액 (조원)",
        template="plotly_white",
        height=420,
        showlegend=False,
    )
    return fig


def _summary_card_html(label: str, summary: dict) -> str:
    if not summary or "error" in summary:
        return f"<div class='card'><h3>{label}</h3><p>데이터 없음</p></div>"
    return dedent(f"""
    <div class='card'>
      <h3>{label}</h3>
      <table>
        <tr><td>자사 값</td><td><b>{summary['value']/1e12:,.2f} 조원</b></td></tr>
        <tr><td>Peer 중위</td><td>{summary['median']/1e12:,.2f} 조원</td></tr>
        <tr><td>순위</td><td>{summary['rank']} / {summary['n_peers']}</td></tr>
        <tr><td>백분위</td><td>{summary['percentile']:.1f}%</td></tr>
        <tr><td>중위 대비</td><td>{summary['value']/summary['median']:,.2f}x</td></tr>
      </table>
    </div>
    """).strip()


PAGE_CSS = """
<style>
  body { font-family: -apple-system, "Malgun Gothic", "Noto Sans KR", sans-serif;
         max-width: 1200px; margin: 24px auto; padding: 0 16px; color: #1f2937; }
  h1 { color: #1F4E79; border-bottom: 3px solid #1F4E79; padding-bottom: 8px; }
  h2 { color: #1F4E79; margin-top: 32px; }
  .meta { color: #6b7280; font-size: 0.9em; }
  .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
           gap: 12px; margin: 16px 0; }
  .card { background: #f9fafb; border-left: 4px solid #F59E0B; padding: 12px 16px;
          border-radius: 6px; }
  .card h3 { margin: 0 0 8px 0; font-size: 0.95em; color: #374151; }
  .card table { width: 100%; font-size: 0.9em; }
  .card td:first-child { color: #6b7280; }
  .card td:last-child { text-align: right; }
  .footer { color: #9ca3af; font-size: 0.85em; margin-top: 48px; border-top: 1px solid #e5e7eb;
            padding-top: 12px; }
</style>
"""


def build_html_report(
    con: duckdb.DuckDBPyConnection,
    output_path: Path,
    report_date: str = "20251231",
    period_instant: str = "2025-12-31",
    period_start: str = "2025-01-01",
    period_end: str = "2025-12-31",
) -> Path:
    """Generate a single self-contained HTML with all charts.

    Layout:
        ┌─ 제목 + 메타
        ├─ 핵심 요약 카드 (보험계약부채, 보험수익, 자산)
        ├─ 차트 1: 보험계약부채 (생보 4개사)
        ├─ 차트 2: 보험계약부채 (전체 11개사) — peer 분포 box
        ├─ 차트 3: 보험수익 (생보 4개사)
        ├─ 차트 4: 보험서비스결과 (생보 4개사)
        └─ 차트 5: 회계모형 분포 (PAA vs Non-PAA, 11개사)
    """
    spec_life = QuerySpec(report_date=report_date, consolidation="consolidated", peer_group="life")
    spec_all = QuerySpec(report_date=report_date, consolidation="consolidated", peer_group="all_insurers")

    life_lib = cross_section.liability_balance(con, spec_life, period_instant=period_instant)
    all_lib = cross_section.liability_balance(con, spec_all, period_instant=period_instant)
    all_assets = cross_section.liability_balance(con, spec_all, item_name="total_assets_bs",
                                                  period_instant=period_instant)
    rev = cross_section.pl_item(con, spec_life, "insurance_revenue", period_start, period_end)
    isr = cross_section.pl_item(con, spec_life, "insurance_service_result", period_start, period_end)
    share = measurement_model.model_share(con, spec_all, period_instant=period_instant)

    self_lib_summary = ratios.self_percentile(life_lib)
    self_lib_all_summary = ratios.self_percentile(all_lib)
    self_asset_summary = ratios.self_percentile(all_assets)
    self_rev_summary = ratios.self_percentile(rev) if not rev.empty else {}

    figs = [
        ("보험계약부채 — 생보 4개사",
         _bar_with_self_highlight(life_lib, "보험계약부채 (생보 4개사)")),
        ("보험계약부채 — 전체 11개사 분포",
         _peer_distribution_box(all_lib, "보험계약부채 — 11개사 분포 (자사 = ★)")),
        ("보험수익 (생보 4개사 · 2025 연간)",
         _bar_with_self_highlight(rev, "보험수익 (생보 4개사)")),
        ("보험서비스결과 (생보 4개사)",
         _bar_with_self_highlight(isr, "보험서비스결과 (생보 4개사)")),
        ("회계모형 분포 (PAA vs Non-PAA, 11개사)",
         _stacked_model_share(share)),
    ]

    chart_htmls = "\n".join(
        f"<h2>{title}</h2>" + fig.to_html(full_html=False, include_plotlyjs="cdn" if i == 0 else False)
        for i, (title, fig) in enumerate(figs)
    )

    cards_html = "<div class='cards'>" + "\n".join([
        _summary_card_html("보험계약부채 (생보 4개사)", self_lib_summary),
        _summary_card_html("보험계약부채 (전체 11개사)", self_lib_all_summary),
        _summary_card_html("자산인 보험계약 (11개사)", self_asset_summary),
        _summary_card_html("보험수익 (생보 4개사)", self_rev_summary),
    ]) + "</div>"

    html = dedent(f"""
    <!doctype html>
    <html lang='ko'>
    <head><meta charset='utf-8'>
    <title>동업사 비교분석 — {report_date[:4]} 사업연도</title>
    {PAGE_CSS}
    </head>
    <body>
      <h1>DART XBRL 동업사 비교분석</h1>
      <p class='meta'>
        대상: 미래에셋생명 (CIK 00112332) · 기준: {report_date[:4]}-12-31<br>
        Peer: KOSPI 상장 보험사 11개사 (생보 4 · 손보 6 · 재보험 1)<br>
        데이터: DART 공시 XBRL 주석 · 결산 후 정정 가능
      </p>
      <h2>핵심 요약</h2>
      {cards_html}
      {chart_htmls}
      <div class='footer'>
        Generated by peer-benchmarking 0.1.0 · DART 데이터 출처: opendart.fss.or.kr
      </div>
    </body></html>
    """).strip()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path
