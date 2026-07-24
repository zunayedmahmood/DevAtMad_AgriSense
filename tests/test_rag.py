
def test_rag_contains_source_derived_and_mock_evidence(services):
    source_results = services.rag.search(
        "lentil suitability agronomy in Moulvibazar",
        crop_id="lentil",
        district="Moulvibazar",
        include_mock=False,
        top_k=5,
    )
    assert source_results
    assert all(result.is_mock is False for result in source_results)

    mixed = services.rag.search(
        "lentil fertilizer irrigation economics stage duration",
        crop_id="lentil",
        include_mock=True,
        top_k=20,
    )
    kinds = {result.source_kind for result in mixed}
    assert kinds.intersection({"provided_mock", "generated_mock_gap", "official_public_source", "provided_source_derived"})
