"""Domain module sanity tests."""

from __future__ import annotations

from peer_benchmarking.domain import liability_mapping, peer_groups


def test_peer_groups_load():
    self_cik = peer_groups.self_cik()
    assert self_cik == "00112332"
    assert peer_groups.name_of(self_cik) == "미래에셋생명"

    life = peer_groups.members_of("life")
    assert self_cik in life
    assert len(life) == 4

    all_ = peer_groups.members_of("all_insurers")
    assert len(all_) == 11


def test_companies_load():
    companies = peer_groups.load_companies()
    assert len(companies) == 11
    sectors = {c.sector for c in companies.values()}
    assert sectors == {"life", "non_life", "reinsurance"}

    self_co = next(c for c in companies.values() if c.is_self)
    assert self_co.cik == "00112332"


def test_liability_dictionary_load():
    d = liability_mapping.load()

    # Balance items
    assert "total_liability" in d.liability_balance
    assert d.liability_balance["total_liability"].element_id == "ifrs-full_InsuranceContractsThatAreLiabilities"

    # Components axis (BEL/RA/CSM)
    assert set(d.components_axis.members) == {"BEL", "RA", "CSM"}
    assert d.components_axis.members["CSM"].element_id == "ifrs-full_ContractualServiceMarginMember"

    # LRC/LIC
    assert "LRC_excl_LossComponent" in d.lrc_lic_axis.members
    assert "LossComponent" in d.lrc_lic_axis.members
    assert "LIC" in d.lrc_lic_axis.members

    # Measurement model
    assert "PAA" in d.measurement_model_axis.members
    assert "NonPAA" in d.measurement_model_axis.members

    # P&L
    assert d.pl_items["insurance_revenue"].element_id == "ifrs-full_InsuranceRevenue"
    assert d.pl_items["insurance_service_result"].element_id == "ifrs-full_InsuranceServiceResult"

    # Roles
    assert d.role_categories()["DI817105"] == "liability_balance"
    assert d.role_categories()["DI817605"] == "pl_finance"

    # Coverage of element_ids
    ids = d.all_element_ids()
    assert len(ids) >= 20


def test_detect_measurement_model():
    assert liability_mapping.detect_measurement_model("일반모형을 적용한 보험계약") == "GMM"
    assert liability_mapping.detect_measurement_model("변동수수료접근법") == "VFA"
    assert liability_mapping.detect_measurement_model("보험료배분접근법 외") == "VFA" or "PAA"
    assert liability_mapping.detect_measurement_model("기타 텍스트") is None
    assert liability_mapping.detect_measurement_model(None) is None
