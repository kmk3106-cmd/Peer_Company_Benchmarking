"""Phase A: BEL/RA/CSM 분해 view — 8개사 횡단 비교.

각 회사 × (BEL, RA, CSM) × (기초·기말 잔액)
+ ratio 계산: RA/BEL, CSM/BEL
+ CSM 증가율 (기말 - 기초) / 기초
"""
from __future__ import annotations
import duckdb
from peer_benchmarking.analysis.fact_fetcher import (
    fetch_components_total, fetch_csm_total_all_variants,
    COMP_BEL, COMP_RA, COMP_CSM,
)

PEERS = [
    ("00112332", "미래에셋생명", "life"),
    ("00126256", "삼성생명",   "life"),
    ("00113058", "한화생명",   "life"),
    ("00117267", "동양생명",   "life"),
    ("00139214", "삼성화재",   "non_life"),
    ("00164973", "현대해상",   "non_life"),
    ("00159102", "DB손해보험", "non_life"),
    ("00135917", "한화손해보험","non_life"),
]


def fmt(v):
    if v is None: return "      —"
    return f"{v/1e8:>9,.0f}억"


def main():
    con = duckdb.connect("data/db/benchmark.duckdb", read_only=True)

    print(f"\n{'='*120}")
    print(f"  BEL/RA/CSM 분해 기말 잔액 (별도·발행, 2025-12-31, 단위 억원)")
    print(f"{'='*120}")

    print(f"\n  {'회사':<14s}  {'sector':<8s}  {'BEL':>11s}  {'RA':>11s}  {'CSM':>11s}  {'합계':>11s}    "
          f"{'RA/BEL':>7s}  {'CSM/BEL':>7s}  {'CSM/합계':>8s}")
    print("─"*120)

    rows = []
    for cik, name, sector in PEERS:
        bel = fetch_components_total(con, cik, "20251231", COMP_BEL, "2025-12-31")
        ra  = fetch_components_total(con, cik, "20251231", COMP_RA,  "2025-12-31")
        csm = fetch_csm_total_all_variants(con, cik, "20251231", "2025-12-31")

        # ratios
        total = (bel or 0) + (ra or 0) + (csm or 0)
        ra_bel = (ra / bel * 100) if bel and ra else None
        csm_bel = (csm / bel * 100) if bel and csm else None
        csm_pct = (csm / total * 100) if total and csm else None

        rows.append({
            "cik": cik, "name": name, "sector": sector,
            "BEL": bel, "RA": ra, "CSM": csm, "TOTAL": total,
            "RA_BEL_pct": ra_bel, "CSM_BEL_pct": csm_bel, "CSM_total_pct": csm_pct,
        })

        def pct(v): return f"{v:>5.1f}%" if v is not None else "    —"
        print(f"  {name:<12s}  {sector:<8s}  {fmt(bel)}  {fmt(ra)}  {fmt(csm)}  {fmt(total)}    "
              f"{pct(ra_bel):>7s}  {pct(csm_bel):>7s}  {pct(csm_pct):>8s}")

    # 기초 잔액 + CSM 증가율
    print(f"\n\n{'='*120}")
    print(f"  CSM 증가율 (기말 vs 기초, FY2025)")
    print(f"{'='*120}")
    print(f"\n  {'회사':<14s}  {'기초 CSM':>11s}  {'기말 CSM':>11s}  {'변동액':>11s}  {'증가율':>10s}")
    print("─"*70)
    for cik, name, sector in PEERS:
        beg = fetch_csm_total_all_variants(con, cik, "20251231", "2024-12-31")
        end = fetch_csm_total_all_variants(con, cik, "20251231", "2025-12-31")
        diff = (end - beg) if (beg is not None and end is not None) else None
        growth = (diff / beg * 100) if (beg and diff is not None) else None
        gstr = f"{growth:>+6.1f}%" if growth is not None else "      —"
        print(f"  {name:<12s}  {fmt(beg)}  {fmt(end)}  {fmt(diff)}  {gstr:>8s}")

    # 자사 (미래에셋) vs 동업사 percentile
    print(f"\n\n{'='*60}")
    print(f"  자사(미래에셋) vs 동업사 percentile (FY2025 기말)")
    print(f"{'='*60}")
    self_row = rows[0]
    for metric, key, suffix in [
        ("BEL", "BEL", "억원"),
        ("RA", "RA", "억원"),
        ("CSM", "CSM", "억원"),
        ("RA/BEL ratio", "RA_BEL_pct", "%"),
        ("CSM/BEL ratio", "CSM_BEL_pct", "%"),
    ]:
        self_val = self_row[key]
        if self_val is None: continue
        others = sorted([r[key] for r in rows[1:] if r[key] is not None])
        n_below = sum(1 for v in others if v < self_val)
        percentile = n_below / len(others) * 100 if others else 0
        unit_fn = (lambda v: f"{v/1e8:,.0f}억") if suffix == "억원" else (lambda v: f"{v:.1f}%")
        print(f"  {metric:<14s}: {unit_fn(self_val):>14s}  → 동업사 7개사 중 {n_below}/{len(others)} 보다 큼 (percentile {percentile:.0f}%)")
        if others:
            print(f"  {'':14s}  동업사: min {unit_fn(min(others))} / median {unit_fn(others[len(others)//2])} / max {unit_fn(max(others))}")


if __name__ == "__main__":
    main()
