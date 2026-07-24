from __future__ import annotations

from pathlib import Path

import pytest

from app.config import Settings
from app.db import AppDatabase
from app.dependencies import Services
from app.services.finance import FinancialCalculator
from app.services.geocoding import GeoapifyClient, LocationNormalizer
from app.services.kb import KnowledgeRepository
from app.services.memory import MemoryService
from app.services.planner import SeasonPlanner
from app.services.rag import HybridRAGStore
from app.services.recommendation import CropRecommender
from app.services.weather import OpenMeteoClient


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def services(tmp_path: Path) -> Services:
    settings = Settings(
        _env_file=None,
        external_mode="offline",
        app_db_path=tmp_path / "runtime.sqlite3",
        rag_db_path=ROOT / "data/processed/rag.sqlite3",
        raw_unified_kb_path=ROOT / "data/raw/bangladesh_agriculture_unified_knowledge.json",
        raw_mock_kb_dir=ROOT / "data/raw/mock_agri_kb",
        generated_kb_path=ROOT / "data/generated/generated_gap_kb.jsonl",
        generated_gazetteer_path=ROOT / "data/generated/mock_location_centroids.json",
    )
    database = AppDatabase(settings.app_db_path)
    kb = KnowledgeRepository(settings)
    rag = HybridRAGStore(settings.rag_db_path)
    normalizer = LocationNormalizer(kb)
    finance = FinancialCalculator(kb)
    memory = MemoryService(database)
    return Services(
        settings=settings,
        database=database,
        kb=kb,
        rag=rag,
        location_normalizer=normalizer,
        geocoder=GeoapifyClient(settings, database, kb),
        weather=OpenMeteoClient(settings, database),
        finance=finance,
        recommender=CropRecommender(kb, rag, finance),
        planner=SeasonPlanner(kb, rag, finance),
        memory=memory,
    )
