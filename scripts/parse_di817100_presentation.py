"""DI817100 presentation tree에서 라인 순서·계층 추출 + ko 라벨 매핑."""
from __future__ import annotations
import xml.etree.ElementTree as ET
from pathlib import Path

PRE = Path("data/raw/mirae_official/entity00112332_2025-12-31_pre.xml")
LAB = Path("data/raw/mirae_official/entity00112332_2025-12-31_lab-ko.xml")

ROLE_URI = "http://dart.fss.or.kr/role/ifrs/dart_2024-06-30_role-DI817100"

ns = {
    "link": "http://www.xbrl.org/2003/linkbase",
    "xlink": "http://www.w3.org/1999/xlink",
    "xbrli": "http://www.xbrl.org/2003/instance",
}

# 1) labels
print("loading labels ...")
labels: dict[str, dict[str, str]] = {}  # locator -> {role: text}
lab_tree = ET.parse(LAB)
loc_map: dict[str, str] = {}  # label -> concept_id
for loc in lab_tree.iter("{http://www.xbrl.org/2003/linkbase}loc"):
    href = loc.get(f"{{{ns['xlink']}}}href", "")
    lbl = loc.get(f"{{{ns['xlink']}}}label", "")
    concept = href.split("#")[-1] if "#" in href else href
    loc_map[lbl] = concept

# label_label -> text (by role)
label_texts: dict[tuple[str, str], str] = {}  # (lbl, role) -> text
for lab in lab_tree.iter("{http://www.xbrl.org/2003/linkbase}label"):
    lbl_id = lab.get(f"{{{ns['xlink']}}}label", "")
    role = lab.get(f"{{{ns['xlink']}}}role", "")
    label_texts[(lbl_id, role)] = lab.text or ""

# labelArc: links loc-label → label-label
loc2labels: dict[str, list[tuple[str, str]]] = {}  # concept_id -> [(role, text)]
for arc in lab_tree.iter("{http://www.xbrl.org/2003/linkbase}labelArc"):
    frm = arc.get(f"{{{ns['xlink']}}}from", "")
    to = arc.get(f"{{{ns['xlink']}}}to", "")
    concept = loc_map.get(frm)
    if not concept:
        continue
    for (lbl_id, role), text in label_texts.items():
        if lbl_id == to:
            loc2labels.setdefault(concept, []).append((role, text))

def get_label(concept: str) -> str:
    """우선순위: standard label > 다른 어떤 거든."""
    entries = loc2labels.get(concept, [])
    std = [t for r, t in entries if r.endswith("/label")]
    if std:
        return std[0]
    return entries[0][1] if entries else f"<{concept}>"

# 2) DI817100 presentation tree
print(f"parsing presentation for role {ROLE_URI} ...")
pre_tree = ET.parse(PRE)
root = pre_tree.getroot()

# Find the presentationLink with this role
for pre_link in root.iter("{http://www.xbrl.org/2003/linkbase}presentationLink"):
    role = pre_link.get(f"{{{ns['xlink']}}}role", "")
    if role != ROLE_URI:
        continue
    # collect locs and arcs
    pre_loc: dict[str, str] = {}
    for loc in pre_link.iter("{http://www.xbrl.org/2003/linkbase}loc"):
        href = loc.get(f"{{{ns['xlink']}}}href", "")
        lbl = loc.get(f"{{{ns['xlink']}}}label", "")
        concept = href.split("#")[-1] if "#" in href else href
        pre_loc[lbl] = concept
    arcs = []  # (parent_label, child_label, order)
    for arc in pre_link.iter("{http://www.xbrl.org/2003/linkbase}presentationArc"):
        frm = arc.get(f"{{{ns['xlink']}}}from", "")
        to = arc.get(f"{{{ns['xlink']}}}to", "")
        order = float(arc.get("order", "0"))
        arcs.append((frm, to, order))

    # Build hierarchy
    children: dict[str, list[tuple[float, str]]] = {}
    parents: set[str] = set()
    all_kids: set[str] = set()
    for frm, to, order in arcs:
        children.setdefault(frm, []).append((order, to))
        parents.add(frm)
        all_kids.add(to)
    roots = [p for p in parents if p not in all_kids]

    def walk(node_lbl: str, depth: int):
        concept = pre_loc.get(node_lbl, "?")
        ko = get_label(concept)
        print(f"  {'  '*depth}[{depth}] {concept[:80]}  →  {ko}")
        for order, kid in sorted(children.get(node_lbl, [])):
            walk(kid, depth + 1)

    print(f"\nroots ({len(roots)}):")
    for r in roots:
        walk(r, 0)

    break
