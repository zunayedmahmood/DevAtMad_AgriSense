
def test_location_cleaning_does_not_send_full_farmer_sentence(services):
    normalized = services.location_normalizer.extract("I have some land in moulovibazar")
    assert normalized.location_text == "Moulvibazar"
    query = services.geocoder._build_query(
        normalized.location_text, normalized.district, normalized.upazila
    )
    assert query == "Moulvibazar, Bangladesh"
    assert "have some land" not in query.lower()


async def test_offline_geocode_is_explicitly_mock(services):
    result = await services.geocoder.geocode("Moulvibazar", district="Moulvibazar")
    assert result["source"] == "generated_mock_geocode"
    assert result["is_mock"] is True
    assert result["query_sent"] == "Moulvibazar, Bangladesh"
