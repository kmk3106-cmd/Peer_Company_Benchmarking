"""Load liability_items.yml and provide typed accessors for the analysis layer.

This module is the single source of truth for which XBRL element_id / axis
member combinations correspond to a given liability or P&L concept in the
IFRS17 footnote data.

Pure functions only — no DB access, no UI. Callers pass a DuckDB connection
(or a DataFrame) to higher-level analysis modules.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml

DEFAULT_YAML = Path(__file__).parent.parent.parent.parent / "data" / "ref" / "liability_items.yml"

PeriodType = Literal["instant", "duration"]
ComponentKey = Literal["BEL", "RA", "CSM"]
ContractTypeKey = Literal["Issued", "ReinsuranceHeld"]
ModelKey = Literal["PAA", "NonPAA", "GMM", "VFA"]


@dataclass(frozen=True)
class ElementSpec:
    """One XBRL concept we care about (a value element or an axis member)."""

    element_id: str
    ko_label: str
    coverage: str | None = None
    period_type: PeriodType | None = None
    desc: str | None = None
    sign: str | None = None


@dataclass(frozen=True)
class AxisSpec:
    """An XBRL axis and its (named) member elements."""

    axis_id: str
    ko_label: str
    members: dict[str, ElementSpec]


@dataclass(frozen=True)
class LiabilityDictionary:
    liability_balance: dict[str, ElementSpec]
    components_axis: AxisSpec
    lrc_lic_axis: AxisSpec
    contract_type_axis: AxisSpec
    measurement_model_axis: AxisSpec
    measurement_model_extension_patterns: dict[str, dict]
    pl_items: dict[str, ElementSpec]
    liability_movement: dict[str, ElementSpec]
    roles: dict[str, dict]

    def all_element_ids(self) -> set[str]:
        """Every named element_id in the dictionary (for coverage checks)."""
        out: set[str] = set()
        for d in (self.liability_balance, self.pl_items, self.liability_movement):
            out |= {e.element_id for e in d.values()}
        for ax in (
            self.components_axis,
            self.lrc_lic_axis,
            self.contract_type_axis,
            self.measurement_model_axis,
        ):
            out.add(ax.axis_id)
            out |= {m.element_id for m in ax.members.values()}
        return out

    def role_categories(self) -> dict[str, str]:
        """Map role code (e.g. 'DI817105') → analysis category."""
        return {code: meta["category"] for code, meta in self.roles.items()}


def _to_element_spec(d: dict) -> ElementSpec:
    return ElementSpec(
        element_id=d["element_id"],
        ko_label=d["ko_label"],
        coverage=d.get("coverage"),
        period_type=d.get("period_type"),
        desc=d.get("desc"),
        sign=d.get("sign"),
    )


def _to_axis_spec(d: dict) -> AxisSpec:
    return AxisSpec(
        axis_id=d["axis_id"],
        ko_label=d["ko_label"],
        members={name: _to_element_spec(member) for name, member in d["members"].items()},
    )


@lru_cache(maxsize=1)
def load(yaml_path: Path | None = None) -> LiabilityDictionary:
    """Load the YAML dictionary. Cached — pass an explicit path to override."""
    path = yaml_path or DEFAULT_YAML
    with path.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return LiabilityDictionary(
        liability_balance={k: _to_element_spec(v) for k, v in raw["liability_balance"].items()},
        components_axis=_to_axis_spec(raw["components_axis"]),
        lrc_lic_axis=_to_axis_spec(raw["lrc_lic_axis"]),
        contract_type_axis=_to_axis_spec(raw["contract_type_axis"]),
        measurement_model_axis=_to_axis_spec(raw["measurement_model_axis"]),
        measurement_model_extension_patterns=raw["measurement_model_extension_patterns"],
        pl_items={k: _to_element_spec(v) for k, v in raw["pl_items"].items()},
        liability_movement={k: _to_element_spec(v) for k, v in raw["liability_movement"].items()},
        roles=raw["roles"],
    )


def detect_measurement_model(label: str | None) -> ModelKey | None:
    """Best-effort GMM/VFA/PAA detection from a Korean/English label.

    For entity-extension members where the standard PAA/NonPAA axis is too coarse.
    """
    if not label:
        return None
    lab = label.lower()
    patterns = load().measurement_model_extension_patterns
    for model_name, spec in patterns.items():
        for kw in spec["label_keywords"]:
            if kw.lower() in lab:
                return model_name  # type: ignore[return-value]
    return None
