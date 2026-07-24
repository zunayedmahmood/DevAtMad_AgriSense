from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from app.config import Settings, get_settings
from app.db import AppDatabase
from app.services.finance import FinancialCalculator
from app.services.geocoding import GeoapifyClient, LocationNormalizer
from app.services.kb import KnowledgeRepository
from app.services.planner import SeasonPlanner
from app.services.rag import HybridRAGStore
from app.services.recommendation import CropRecommender
from app.services.weather import OpenMeteoClient


@dataclass
class Services:
    settings: Settings
    database: AppDatabase
    kb: KnowledgeRepository
    rag: HybridRAGStore
    location_normalizer: LocationNormalizer
    geocoder: GeoapifyClient
    weather: OpenMeteoClient
    finance: FinancialCalculator
    recommender: CropRecommender
    planner: SeasonPlanner


@lru_cache(maxsize=1)
def get_services() -> Services:
    settings = get_settings()
    database = AppDatabase(settings.app_db_path)
    kb = KnowledgeRepository(settings)
    rag = HybridRAGStore(settings.rag_db_path)
    normalizer = LocationNormalizer(kb)
    finance = FinancialCalculator(kb)
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
    )
