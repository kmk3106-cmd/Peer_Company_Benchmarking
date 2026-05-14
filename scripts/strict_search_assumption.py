"""엄격 search — 미래에셋 (entity00112332) 의 '계리적 가정에 의한 보험부채 변동내역' 정확 매칭.

방법:
1. DART XBRL 적재 데이터 (lab_insurers, pre_insurers)
2. 사업보고서 원본 XBRL (data/raw/mirae_official/) — lab-ko.xml, pre.xml

추정·유추 금지. 라벨 정확 일치만 인정.
"""
from __future__ import annotations
import duckdb
import xml.etree.ElementTree as ET
from pathlib import Path

CIK = "00112332"

print("="*100)
print("STEP 1: DART XBRL 적재본에서 '계리' 또는 '가정' 키워드 라벨 search")
print("="*100)

con = duckdb.connect("data/db/benchmark.duckdb", read_only=True)

# 라벨 정확 search
keywords = ["계리적 가정", "계리가정", "계리적가정", "보험부채 변동내역", "가정에 의한", "가정 변경에 따른"]
for kw in keywords:
    rows = con.execute("""
      SELECT DISTINCT l.ELMT_ID, l.LABEL, COUNT(*) AS n
      FROM lab_insurers l
      WHERE l.CIK=? AND l.LANG='ko' AND l.LABEL LIKE ?
      GROUP BY l.ELMT_ID, l.LABEL
      ORDER BY n DESC LIMIT 10
    """, [CIK, f"%{kw}%"]).fetchall()
    print(f"\n  키워드 '{kw}': {len(rows)} 매치")
    for eid, label, n in rows[:5]:
        eshort = eid.replace("ifrs-full_","").replace("dart_","d:").replace(f"entity{CIK}_","#")[:70]
        print(f"    [{n:>4d}] {eshort:<72s} ← {label[:60]}")


print("\n\n" + "="*100)
print("STEP 2: 사업보고서 원본 XBRL lab-ko.xml 정확 search")
print("="*100)

lab_path = Path("data/raw/mirae_official/entity00112332_2025-12-31_lab-ko.xml")
if lab_path.exists():
    tree = ET.parse(lab_path)
    NS = {"link": "http://www.xbrl.org/2003/linkbase",
          "xlink": "http://www.w3.org/1999/xlink"}

    # 모든 label 추출
    labels = []
    for lab in tree.iter(f"{{{NS['link']}}}label"):
        text = lab.text or ""
        role = lab.get(f"{{{NS['xlink']}}}role", "")
        lbl_id = lab.get(f"{{{NS['xlink']}}}label", "")
        labels.append({"text": text, "role": role, "label_id": lbl_id})

    print(f"\n  pre.xml 총 라벨 {len(labels)}개. '계리' 또는 '가정' 키워드 search:\n")
    for kw in ["계리적 가정", "계리가정", "보험부채 변동내역", "가정에 의한", "가정 변경", "할인율 변경", "할인률 변경"]:
        matches = [l for l in labels if kw in l["text"]]
        if matches:
            print(f"  ── '{kw}' ({len(matches)} 매치)")
            for m in matches[:8]:
                role_short = m["role"].split("/")[-1] if m["role"] else ""
                print(f"    [{role_short:<20s}] {m['text'][:80]}")
        else:
            print(f"  ── '{kw}' — 매치 없음")
else:
    print(f"  ⚠ {lab_path} 없음")


print("\n\n" + "="*100)
print("STEP 3: presentation tree에서 '계리' 또는 '가정' 키워드 role search")
print("="*100)

pre_path = Path("data/raw/mirae_official/entity00112332_2025-12-31_pre.xml")
if pre_path.exists():
    pre_tree = ET.parse(pre_path)
    # roleRef + roleURI 찾기 + 그 role의 라벨에 키워드 포함되나
    for roleref in pre_tree.iter(f"{{{NS['link']}}}roleRef"):
        role_uri = roleref.get("roleURI", "")
        if "DI8" in role_uri or "U8" in role_uri:
            # 이 role에서 사용된 element 라벨에 '계리' 또는 '가정' 포함 element 검색
            pass

    # 더 빠른 방법: pre.xml 텍스트에 '계리' 또는 '가정' 키워드 grep
    raw = pre_path.read_text(encoding="utf-8")
    # 그냥 element_id에 패턴 찾기
    import re
    pattern_assumption = re.compile(r'ActuarialAssumption|AssumptionChange|GeneralAssumption|할인율|할인률|위험율|해지율', re.IGNORECASE)
    matches = set(pattern_assumption.findall(raw))
    print(f"\n  pre.xml에서 가정 관련 패턴 매치: {matches or '없음'}")
else:
    print(f"  ⚠ {pre_path} 없음")
