from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from app.config import Settings, get_settings
from app.db import AppDatabase
from app.services.finance import FinancialCalculator
from app.services.geocoding import GeoapifyClient, LocationNormalizer
from app.services.kb import KnowledgeRepository
from app.services.memory import MemoryService
from app.services.mixed_catalog import MixedCatalogRepository
from app.services.planner import SeasonPlanner
from app.services.rag import HybridRAGStore
from app.services.recommendation import CropRecommender
from app.services.weather import OpenMeteoClient
from app.services.verifier import PlanVerifier
from app.services.repair import RepairService
from app.services.scenario import ScenarioSimulator


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
    memory: MemoryService
    verifier: PlanVerifier | None = None
    repair: RepairService | None = None
    scenario: ScenarioSimulator | None = None
    catalog: MixedCatalogRepository | None = None
    controller: Any = None
    fallback_agent: Any = None


@lru_cache(maxsize=1)
def get_services() -> Services:
    settings = get_settings()
    database = AppDatabase(settings.app_db_path)
    kb = KnowledgeRepository(settings)
    rag = HybridRAGStore(settings.rag_db_path)
    catalog = MixedCatalogRepository(settings.mixed_catalog_db_path)
    normalizer = LocationNormalizer(kb)
    finance = FinancialCalculator(kb)
    memory = MemoryService(database)
    verifier = PlanVerifier()
    repair = RepairService()
    scenario = ScenarioSimulator(verifier)

    srv = Services(
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
        verifier=verifier,
        repair=repair,
        scenario=scenario,
        catalog=catalog,
    )

    from app.services.agent import TierZeroAgent
    from app.services.openai_agent import OpenAIAgenticEngine
    from app.agent.controller import AgentController

    tier_zero = TierZeroAgent(srv)
    openai_engine = OpenAIAgenticEngine(srv)
    srv.fallback_agent = openai_engine
    srv.controller = AgentController(srv)

    return srv
