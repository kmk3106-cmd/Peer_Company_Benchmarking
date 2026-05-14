"""§5-G 변동표 라인 매트릭스에 기시/기말 잔액 추가.

기시잔액 (2024-12-31, IssuedThatAreLiabilities net)
기말잔액 (2025-12-31, IssuedThatAreLiabilities net)
"""
from __future__ import annotations
import json
from pathlib import Path
import duckdb
from peer_benchmarking.analysis.fact_fetcher import fetch_balance_separate_issued

PEER_CIKS = ["00112332", "00126256", "00113058", "00117267",
             "00139214", "00164973", "00159102", "00135917"]

con = duckdb.connect("data/db/benchmark.duckdb", read_only=True)

# 기시·기말 잔액 추출
balance_rows = {"기초 잔액 (2024-12-31)": {}, "기말 잔액 (2025-12-31)": {}}
for cik in PEER_CIKS:
    beg = fetch_balance_separate_issued(con, cik, "20251231", "2024-12-31")
    end = fetch_balance_separate_issued(con, cik, "20251231", "2025-12-31")
    balance_rows["기초 잔액 (2024-12-31)"][cik] = beg
    balance_rows["기말 잔액 (2025-12-31)"][cik] = end
    print(f"  {cik}: 기초 {beg/1e8 if beg else 0:>10,.0f}억  기말 {end/1e8 if end else 0:>10,.0f}억")

# 기존 line_values_matrix 에 병합
matrix = json.loads(Path("report/line_values_matrix.json").read_text(encoding="utf-8"))
# 기초를 맨 앞, 기말을 맨 뒤에 삽입
new_matrix = {"기초 잔액 (2024-12-31)": balance_rows["기초 잔액 (2024-12-31)"]}
new_matrix.update(matrix)
new_matrix["기말 잔액 (2025-12-31)"] = balance_rows["기말 잔액 (2025-12-31)"]

Path("report/line_values_matrix.json").write_text(
    json.dumps(new_matrix, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\n매트릭스 업데이트: {len(new_matrix)} 라인")
