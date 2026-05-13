"""미래에셋생명 (CIK 00112332) 모든 XBRL 값 펼침 Excel.

사용자가 사업보고서/내부 결산 데이터와 직접 대조 검증할 수 있도록
context의 모든 axis 조합을 한 행에 함께 표시한다.

출력: report/mirae_dump.xlsx
  시트 1: 잔액_instant     — period_instant 시점의 모든 KRW 값
  시트 2: 변동_duration   — period_start/end 구간의 모든 KRW 값
  시트 3: 손익_duration   — 잔액 시트와 동일 (참조 편의)
  시트 4: 부채_관련만     — 라벨에 '보험' 또는 'Insurance' 포함만
  시트 5: master_elements — 모든 element_id ↔ 한국어 라벨 사전
"""

from __future__ import annotations

import logging
from pathlib import Path

import duckdb
import pandas as pd

CIK = "00112332"
log = logging.getLogger(__name__)


DUMP_SQL = """
WITH mirae AS (
  SELECT v.ELEMENT_ID, v.CONTEXT_ID, v.UNIT_ID, v.DECIMALS,
         v.amount_krw, v.raw_value
  FROM val_insurers v
  WHERE v.CIK = ?
    AND v.UNIT_ID = 'KRW'
    AND v.amount_krw IS NOT NULL
),
dims AS (
  SELECT
    CONTEXT_ID,
    STRING_AGG(AXIS_ELEMENT_ID || '=' || MEMBER_ELEMENT_ID, ' | '
               ORDER BY AXIS_ELEMENT_ID) AS dimensions,
    ANY_VALUE(PERIOD_START_DATE) AS period_start,
    ANY_VALUE(PERIOD_END_DATE)   AS period_end,
    ANY_VALUE(PERIOD_INSTANT)    AS period_instant
  FROM cntxt_insurers
  WHERE CIK = ?
  GROUP BY CONTEXT_ID
),
labels AS (
  SELECT ELMT_ID,
         MAX(CASE WHEN LANG='ko' THEN LABEL END) AS ko_label,
         MAX(CASE WHEN LANG='en' THEN LABEL END) AS en_label
  FROM lab_insurers
  WHERE CIK = ?
    AND LABEL_ROLE_URI = 'http://www.xbrl.org/2003/role/label'
  GROUP BY ELMT_ID
)
SELECT
  m.ELEMENT_ID                          AS element_id,
  COALESCE(l.ko_label, l.en_label, '')  AS label,
  d.dimensions,
  d.period_start, d.period_end, d.period_instant,
  m.amount_krw,
  (m.amount_krw / 1e12)                 AS amount_trillion,
  m.DECIMALS                            AS decimals,
  m.raw_value
FROM mirae m
LEFT JOIN dims d   ON d.CONTEXT_ID = m.CONTEXT_ID
LEFT JOIN labels l ON l.ELMT_ID    = m.ELEMENT_ID
ORDER BY ABS(m.amount_krw) DESC
"""


def _shorten_dims(s: str | None) -> str:
    """Drop ifrs-full_/dart_ prefixes in dimensions for readability."""
    if not s:
        return ""
    return (
        s.replace("ifrs-full_", "")
        .replace("dart-gcd_", "")
        .replace("dart_2024-06-30_", "")
        .replace("dart_", "")
    )


def _shorten_element(e: str) -> str:
    return (
        e.replace("ifrs-full_", "")
        .replace("dart-gcd_", "")
        .replace("dart_", "")
    )


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    db_path = Path("data/db/benchmark.duckdb")
    out = Path("report/mirae_dump.xlsx")

    if not db_path.exists():
        log.error("DB not found: %s", db_path)
        return 2

    con = duckdb.connect(str(db_path), read_only=True)
    log.info("querying CIK %s ...", CIK)
    df = con.execute(DUMP_SQL, [CIK, CIK, CIK]).df()
    con.close()

    log.info("rows: %s", f"{len(df):,}")

    # Readable columns
    df["element_short"] = df["element_id"].map(_shorten_element)
    df["dimensions_short"] = df["dimensions"].map(_shorten_dims)

    # Categorize by period type
    instant_df = df[df["period_instant"].notna() & (df["period_instant"] != "")].copy()
    duration_df = df[df["period_start"].notna() & (df["period_start"] != "")].copy()

    # Liability-related filter (label OR element_id contains insurance keywords)
    kw = r"보험|Insurance|Reinsurance|재보험"
    liab_df = df[
        df["label"].str.contains(kw, na=False, regex=True)
        | df["element_id"].str.contains(kw, na=False, regex=True)
    ].copy()

    # Master element list (one row per unique element + label)
    master = (
        df.groupby(["element_id", "label"], dropna=False)
        .agg(
            n_contexts=("CONTEXT_ID" if "CONTEXT_ID" in df.columns else "element_id", "count"),
            max_abs=("amount_krw", lambda s: s.abs().max()),
        )
        .reset_index()
        .sort_values("max_abs", ascending=False)
    )
    master["element_short"] = master["element_id"].map(_shorten_element)
    master["max_abs_trillion"] = (master["max_abs"] / 1e12).round(3)

    out.parent.mkdir(parents=True, exist_ok=True)
    log.info("writing %s ...", out)
    with pd.ExcelWriter(out, engine="openpyxl") as xw:
        cols_inst = [
            "element_short", "label", "dimensions_short",
            "period_instant", "amount_trillion", "amount_krw", "decimals",
            "element_id",
        ]
        instant_df[cols_inst].to_excel(xw, sheet_name="잔액_instant", index=False)

        cols_dur = [
            "element_short", "label", "dimensions_short",
            "period_start", "period_end", "amount_trillion", "amount_krw", "decimals",
            "element_id",
        ]
        duration_df[cols_dur].to_excel(xw, sheet_name="변동_duration", index=False)

        # 부채 관련만 — period 무관, 사람이 보기 편한 순서
        liab_df[["element_short", "label", "dimensions_short",
                 "period_instant", "period_start", "period_end",
                 "amount_trillion", "amount_krw", "decimals", "element_id"]
                ].to_excel(xw, sheet_name="부채_관련만", index=False)

        master[["element_short", "label", "n_contexts", "max_abs_trillion", "element_id"]
               ].to_excel(xw, sheet_name="master_elements", index=False)

    log.info("done: %s (%.1f KB)", out, out.stat().st_size / 1024)
    log.info("=== summary ===")
    log.info("  total rows               : %s", f"{len(df):,}")
    log.info("  instant rows             : %s", f"{len(instant_df):,}")
    log.info("  duration rows            : %s", f"{len(duration_df):,}")
    log.info("  liability-related rows   : %s", f"{len(liab_df):,}")
    log.info("  unique elements          : %s", f"{len(master):,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
