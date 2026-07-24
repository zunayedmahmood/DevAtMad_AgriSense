
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


def test_evidence_classification_block_discipline(services):
    from app.api.routes import kb_stats
    stats = kb_stats()
    assert "evidence_classification" in stats
    clf = stats["evidence_classification"]
    assert "real_or_reviewed" in clf
    assert "seeded_demonstration_assumptions" in clf
    assert "calculated_by_code" in clf
    assert "AgriSense never promotes seeded demonstration assumptions into public evidence" in clf["judge_statement"]

