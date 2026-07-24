
async def test_offline_weather_is_labeled_and_has_decision_summary(services):
    result = await services.weather.forecast(23.5, 90.2, days=7)
    assert result["source"] == "generated_mock_weather"
    assert result["is_mock"] is True
    assert len(result["days"]) == 7
    assert "rainfall_next_72h_mm" in result["summary"]
    assert result["summary"]["forecast_end"] == result["days"][-1]["date"]
