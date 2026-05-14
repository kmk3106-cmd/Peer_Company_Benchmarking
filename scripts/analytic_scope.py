"""Step 3: 8개사 계리적 비교 가능성 판단.

산출:
1) 라인별 cross-tab (21 라인 × 8개사)
2) 공통 비교 가능 라인 셋 (생보·손보·전체)
3) 2가지 view 별 비교 추천 (BEL/RA/CSM vs 상품군)
4) 손보용 상품군 보강 매핑 (장기/일반/자동차)
"""
from __future__ import annotations
import json, re, csv
from pathlib import Path

DETAILS = json.loads(Path("report/feasibility_details.json").read_text(encoding="utf-8"))

LIFE = ["00112332", "00126256", "00113058", "00117267"]  # 미래/삼성/한화/동양
NONLIFE = ["00139214", "00164973", "00159102", "00135917"]  # 삼성화재/현대/DB/한화손보
ALL = LIFE + NONLIFE

# 표준 라인 (peer_feasibility.py 와 동일)
STANDARD_LINES = [
    "기초잔액", "기초잔액_자산", "기초잔액_부채",
    "보험수익", "신계약인식", "CSM조정추정변동", "CSM미조정추정변동",
    "위험조정변동", "경험조정", "과거서비스변동",
    "손실부담계약손실", "발생사고요소조정", "발생사고비용",
    "수취보험료", "지급보험금", "보험취득CF지급", "보험취득CF상각",
    "투자요소", "금융손익_PL", "금융손익_OCI", "기타증감",
]

# 손보 상품군 매핑 룰 (보강)
NONLIFE_PRODUCT_RULES = [
    (10, r"장기|long.?term", "장기"),
    (10, r"자동차|auto|motor", "자동차"),
    (10, r"일반|general", "일반"),
    (8,  r"건강|health|질병|암", "장기"),   # 손보의 건강은 보통 장기
    (8,  r"저축|savings", "장기"),
    (5,  r"OtherInsuranceMember$|기타", "기타"),
]


def classify_nonlife(ko_label: str, element_id: str) -> tuple[str, int]:
    text = (ko_label or "") + " " + (element_id or "")
    best = ("미분류", 0)
    for prio, pat, group in NONLIFE_PRODUCT_RULES:
        if re.search(pat, text, re.IGNORECASE):
            if prio > best[1]:
                best = (group, prio)
    return best


# ────────────────────────────────────────────────────────────────
# 1) 라인별 cross-tab
# ────────────────────────────────────────────────────────────────
print("="*100)
print("1) 라인별 cross-tab (21 표준 라인 × 8개사)")
print("="*100)

line_matrix = {}  # {line: {cik: True/False}}
for line in STANDARD_LINES:
    line_matrix[line] = {}
    for cik in ALL:
        d = DETAILS[cik]
        rep = any(L["line"] == line and L["reported"] for L in d["standard_lines"])
        line_matrix[line][cik] = rep

# header
names = {cik: DETAILS[cik]["company"] for cik in ALL}
print(f"\n{'라인':<24s}  {'미래':>4s}{'삼성':>4s}{'한화':>4s}{'동양':>4s}  {'삼화':>4s}{'현대':>4s}{'DB':>4s}{'한손':>4s}  합계 (생/손)")
print("─"*100)
for line in STANDARD_LINES:
    cells = []
    n_life = 0
    n_nonlife = 0
    for cik in ALL:
        v = line_matrix[line][cik]
        cells.append("✓" if v else "·")
        if v:
            if cik in LIFE: n_life += 1
            else: n_nonlife += 1
    print(f"  {line:<22s}  {cells[0]:>4s}{cells[1]:>4s}{cells[2]:>4s}{cells[3]:>4s}  "
          f"{cells[4]:>4s}{cells[5]:>4s}{cells[6]:>4s}{cells[7]:>4s}   "
          f"{n_life+n_nonlife:>2d}/8 ({n_life}/{n_nonlife})")


# ────────────────────────────────────────────────────────────────
# 2) 공통 비교 가능 라인 셋 (≥ 6/8 = 75% 보고)
# ────────────────────────────────────────────────────────────────
print("\n\n" + "="*100)
print("2) 공통 비교 가능 라인 셋")
print("="*100)

common_all = []      # 8/8
common_75 = []       # ≥6/8
common_life = []     # ≥3/4 생보
common_nonlife = []  # ≥3/4 손보

for line in STANDARD_LINES:
    n_life = sum(1 for cik in LIFE if line_matrix[line][cik])
    n_nonlife = sum(1 for cik in NONLIFE if line_matrix[line][cik])
    n_total = n_life + n_nonlife
    if n_total == 8:
        common_all.append(line)
    if n_total >= 6:
        common_75.append((line, n_total))
    if n_life >= 3:
        common_life.append((line, n_life))
    if n_nonlife >= 3:
        common_nonlife.append((line, n_nonlife))

print(f"\n  ★ 전 회사(8/8) 공통: {len(common_all)}개")
for L in common_all: print(f"    - {L}")

print(f"\n  ★ 75% 이상(≥6/8) 보고: {len(common_75)}개")
for L, n in common_75: print(f"    - {L} ({n}/8)")

print(f"\n  ★ 생보 4개사 중 ≥3 보고: {len(common_life)}개")
for L, n in common_life: print(f"    - {L} ({n}/4)")

print(f"\n  ★ 손보 4개사 중 ≥3 보고: {len(common_nonlife)}개")
for L, n in common_nonlife: print(f"    - {L} ({n}/4)")


# ────────────────────────────────────────────────────────────────
# 3) 2가지 view 별 비교 추천
# ────────────────────────────────────────────────────────────────
print("\n\n" + "="*100)
print("3) View 별 비교 추천")
print("="*100)

print("""
View A: BEL/RA/CSM 분해 (IFRS17 §103)
──────────────────────────────────────
  대상: 8개사 전부 (BEL/RA/CSM 모두 ✓)
  비교 가능 cell: line × {BEL, RA, CSM} × 8개사
  강점: 표준 axis (회사간 정의 동일)
  약점: 일부 회사는 CSM transition member 만 사용 (BEL/RA/CSM 비공식 분해)

  추천 비교 분석:
  - 기말 잔액 BEL/RA/CSM ratio (회사별 보수성 차이 시그널)
  - CSM 증가율 (신계약 효과)
  - RA 비율 (위험 부담 수준)
  - 보험금융손익 → BEL 영향 vs CSM 영향

View B: 상품군 분해 (TypesOfContractsAxis)
──────────────────────────────────────────
  대상: 생보 4개사 + 손보 4개사 분리
  생보 5분류: 사망/건강/연금/저축/기타
  손보 4분류 (보강): 장기/자동차/일반/기타
  강점: 사업 mix 의미 직접 비교
  약점: 회사별 axis 멤버 정의 다름, 매핑 후처리 필수

  추천 비교 분석:
  - 생보: 사망보장 비중, 변액(저축+연금) 비중
  - 손보: 장기:자동차:일반 mix
""")


# ────────────────────────────────────────────────────────────────
# 4) 손보 상품군 보강 매핑
# ────────────────────────────────────────────────────────────────
print("="*100)
print("4) 손보 상품군 매핑 (보강: 장기/자동차/일반/기타)")
print("="*100)

for cik in NONLIFE:
    name = DETAILS[cik]["company"]
    print(f"\n  ── {name} ({cik}) ──")
    new_dist = {"장기":0, "자동차":0, "일반":0, "기타":0, "미분류":0}
    relabeled = []
    for t in DETAILS[cik]["types_members"]:
        new_group, conf = classify_nonlife(t["ko_label"], t["member"])
        new_dist[new_group] += 1
        relabeled.append({
            "member": t["member"][:60],
            "ko": t["ko_label"],
            "old_group": t["std_group"],
            "new_group": new_group,
            "confidence": conf,
        })
    print(f"    매핑 분포: {new_dist}")
    for r in relabeled:
        flag = "★" if r["new_group"] != r["old_group"] else " "
        print(f"     {flag} [{r['old_group']:>4s} → {r['new_group']:>4s}]  {r['ko']}")


# ────────────────────────────────────────────────────────────────
# 산출물 저장
# ────────────────────────────────────────────────────────────────
scope = {
    "common_all_8": common_all,
    "common_75pct": [{"line": L, "n": n} for L, n in common_75],
    "common_life_75pct": [{"line": L, "n": n} for L, n in common_life],
    "common_nonlife_75pct": [{"line": L, "n": n} for L, n in common_nonlife],
    "view_A_BEL_RA_CSM": {
        "available_peers": ALL,
        "recommended": [
            "기말 BEL/RA/CSM ratio (보수성 시그널)",
            "CSM 증가율 (신계약 효과)",
            "RA 비율 (위험 부담 수준)",
            "보험금융손익 → BEL 영향 vs CSM 영향",
        ],
    },
    "view_B_product": {
        "life_peers": LIFE,
        "life_groups": ["사망", "건강", "연금", "저축", "기타"],
        "nonlife_peers": NONLIFE,
        "nonlife_groups": ["장기", "자동차", "일반", "기타"],
        "recommended": [
            "생보: 사망보장 비중, 변액 비중",
            "손보: 장기:자동차:일반 mix",
        ],
    },
}
Path("report/analytic_scope.json").write_text(
    json.dumps(scope, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\n\nwrote report/analytic_scope.json")

# Cross-tab CSV
csv_path = Path("report/line_crosstab.csv")
with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["line"] + [DETAILS[c]["company"] for c in ALL] + ["n_life", "n_nonlife", "n_total"])
    for line in STANDARD_LINES:
        row = [line]
        for cik in ALL:
            row.append("Y" if line_matrix[line][cik] else "N")
        n_life = sum(1 for c in LIFE if line_matrix[line][c])
        n_nonlife = sum(1 for c in NONLIFE if line_matrix[line][c])
        row.extend([n_life, n_nonlife, n_life + n_nonlife])
        w.writerow(row)
print(f"wrote {csv_path}")
