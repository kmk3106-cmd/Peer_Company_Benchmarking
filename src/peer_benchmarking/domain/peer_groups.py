"""Load peer_groups.yml and companies.csv. Pure mapping — no DB."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

REF_DIR = Path(__file__).parent.parent.parent.parent / "data" / "ref"


@dataclass(frozen=True)
class Company:
    cik: str
    name_ko: str
    name_en: str
    sector: str  # "life" | "non_life" | "reinsurance"
    is_self: bool
    listing: str


@dataclass(frozen=True)
class PeerGroup:
    label: str
    description: str
    members: tuple[str, ...]  # CIKs


@lru_cache(maxsize=1)
def load_companies() -> dict[str, Company]:
    """CIK → Company. Cached."""
    path = REF_DIR / "companies.csv"
    out: dict[str, Company] = {}
    with path.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out[r["cik"]] = Company(
                cik=r["cik"],
                name_ko=r["name_ko"],
                name_en=r["name_en"],
                sector=r["sector"],
                is_self=r["is_self"].lower() == "true",
                listing=r["listing"],
            )
    return out


@lru_cache(maxsize=1)
def load_groups() -> tuple[str, dict[str, PeerGroup]]:
    """Returns (self_cik, {group_name: PeerGroup})."""
    path = REF_DIR / "peer_groups.yml"
    with path.open(encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    groups = {
        name: PeerGroup(
            label=g["label"],
            description=g["description"],
            members=tuple(g["members"]),
        )
        for name, g in cfg["groups"].items()
    }
    return cfg["self_cik"], groups


def self_cik() -> str:
    return load_groups()[0]


def members_of(group_name: str) -> tuple[str, ...]:
    return load_groups()[1][group_name].members


def name_of(cik: str) -> str:
    """Pretty Korean name for a CIK, falls back to CIK itself if unknown."""
    c = load_companies().get(cik)
    return c.name_ko if c else cik
