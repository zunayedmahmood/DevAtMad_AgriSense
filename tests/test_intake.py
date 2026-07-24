from app.schemas import FarmProfile
from app.services.intake import IntakeParser


def test_complete_profile_is_extracted(services):
    parser = IntakeParser(services.kb, services.location_normalizer)
    parsed = parser.parse(
        "I have 2 acres of sandy-loam land in Moulovibazar. My budget is 80000 taka, "
        "I have limited irrigation, and I want the rabi season.",
        FarmProfile(),
    )
    profile = parser.merge(FarmProfile(), parsed, None)
    assert profile.location_text == "Moulvibazar"
    assert profile.district == "Moulvibazar"
    assert profile.farm_size_acre == 2
    assert profile.soil_type == "sandy_loam"
    assert profile.water_availability == "limited"
    assert profile.budget_bdt == 80000
    assert profile.target_season == "rabi"
    assert parser.missing_fields(profile) == []


def test_only_missing_fields_are_asked(services):
    parser = IntakeParser(services.kb, services.location_normalizer)
    parsed = parser.parse("I have land in Rangpur", FarmProfile())
    profile = parser.merge(FarmProfile(), parsed, None)
    missing = parser.missing_fields(profile)
    assert "location_text" not in missing
    assert missing == [
        "farm_size_acre",
        "soil_type",
        "water_availability",
        "budget_bdt",
        "target_season",
    ]


def test_single_small_pump_does_not_become_reliable_irrigation(services):
    parser = IntakeParser(services.kb, services.location_normalizer)
    parsed = parser.parse(
        "I have 5 acres in Rangpur with one small pump that draws a good amount of water. "
        "Budget 200000 taka, loam soil, rabi season.",
        FarmProfile(),
    )
    profile = parser.merge(FarmProfile(), parsed, None)
    assert profile.water_availability is None
    assert parsed.clarifications
    assert "cover all 5 acres" in parsed.clarifications[0]
