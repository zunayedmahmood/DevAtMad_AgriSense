from __future__ import annotations

import pytest
from pathlib import Path

from app.config import Settings
from app.db import AppDatabase
from app.dependencies import Services
from app.schemas import AgentTurnRequest, FarmProfile, MemoryContext
from app.services.agent import TierZeroAgent
from app.services.finance import FinancialCalculator
from app.services.geocoding import GeoapifyClient, LocationNormalizer
from app.services.gemini_agent import GeminiAgenticEngine
from app.services.kb import KnowledgeRepository
from app.services.memory import MemoryService
from app.services.planner import SeasonPlanner
from app.services.rag import HybridRAGStore
from app.services.recommendation import CropRecommender
from app.services.weather import OpenMeteoClient


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def test_services(tmp_path: Path) -> Services:
    settings = Settings(
        _env_file=None,
        external_mode="offline",
        app_db_path=tmp_path / "test_agrisense.sqlite3",
        rag_db_path=ROOT / "data/processed/rag.sqlite3",
        raw_unified_kb_path=ROOT / "data/raw/bangladesh_agriculture_unified_knowledge.json",
        raw_mock_kb_dir=ROOT / "data/raw/mock_agri_kb",
        generated_kb_path=ROOT / "data/generated/generated_gap_kb.jsonl",
        generated_gazetteer_path=ROOT / "data/generated/mock_location_centroids.json",
    )
    db = AppDatabase(settings.app_db_path)
    kb = KnowledgeRepository(settings)
    rag = HybridRAGStore(settings.rag_db_path)
    normalizer = LocationNormalizer(kb)
    finance = FinancialCalculator(kb)
    memory = MemoryService(db)
    return Services(
        settings=settings,
        database=db,
        kb=kb,
        rag=rag,
        location_normalizer=normalizer,
        geocoder=GeoapifyClient(settings, db, kb),
        weather=OpenMeteoClient(settings, db),
        finance=finance,
        recommender=CropRecommender(kb, rag, finance),
        planner=SeasonPlanner(kb, rag, finance),
        memory=memory,
    )


@pytest.mark.asyncio
async def test_persistent_memory_across_sessions(test_services: Services):
    agent = TierZeroAgent(test_services)
    farmer_id = "farmer_test_101"

    # Session 1: Complete farm setup and plan creation
    r1 = await agent.turn(
        AgentTurnRequest(
            session_id="session_1",
            farmer_id=farmer_id,
            message="I have 2 acres land in Rangpur, loam soil, reliable irrigation, BDT 200000 budget, targeting Rabi.",
        )
    )
    assert r1.status == "awaiting_crop_selection"

    r2 = await agent.turn(
        AgentTurnRequest(
            session_id="session_1",
            farmer_id=farmer_id,
            message="Select maize",
            auto_select_top_crop=True,
        )
    )
    assert r2.status == "plan_ready"
    assert r2.memory.farm_id is not None
    saved_farm_id = r2.memory.farm_id

    # Session 2: Fresh session ID, same farmer identity
    r3 = await agent.turn(
        AgentTurnRequest(
            session_id="session_2",
            farmer_id=farmer_id,
            message="Plan another season for my Rangpur farm.",
        )
    )
    assert r3.status == "needs_memory_confirmation"
    assert len(r3.memory.saved_farms) == 1
    assert r3.memory.saved_farms[0].farm_id == saved_farm_id

    # Confirm applying saved memory
    r4 = await agent.turn(
        AgentTurnRequest(
            session_id="session_2",
            farmer_id=farmer_id,
            farm_id=saved_farm_id,
            memory_action="apply",
            message="Use saved farm",
        )
    )
    assert r4.profile.farm_size_acre == 2.0
    assert r4.profile.soil_type == "loam"
    assert r4.profile.water_availability == "reliable"


@pytest.mark.asyncio
async def test_memory_does_not_restore_old_crop_or_weather(test_services: Services):
    agent = TierZeroAgent(test_services)
    farmer_id = "farmer_test_102"

    r1 = await agent.turn(
        AgentTurnRequest(
            session_id="session_s1",
            farmer_id=farmer_id,
            message="Rangpur, 2 acres, loam soil, reliable irrigation, BDT 200000 budget, Rabi season.",
            auto_select_top_crop=True,
        )
    )
    assert r1.status == "plan_ready"
    farm_id = r1.memory.farm_id

    # New session restoring farm profile
    r2 = await agent.turn(
        AgentTurnRequest(
            session_id="session_s2",
            farmer_id=farmer_id,
            farm_id=farm_id,
            memory_action="apply",
            message="Plan Kharif-1 for my farm",
        )
    )
    # Target crop should NOT be auto-filled from session 1
    assert r2.profile.chosen_crop_id is None
    assert r2.profile.farm_size_acre == 2.0


@pytest.mark.asyncio
async def test_farmer_isolation(test_services: Services):
    agent = TierZeroAgent(test_services)

    # Farmer A creates farm
    await agent.turn(
        AgentTurnRequest(
            session_id="sess_fa",
            farmer_id="farmer_a",
            message="Rangpur 2 acres loam reliable irrigation BDT 200000 Rabi maize",
            auto_select_top_crop=True,
        )
    )

    # Farmer B queries for Rangpur farm
    r_b = await agent.turn(
        AgentTurnRequest(
            session_id="sess_fb",
            farmer_id="farmer_b",
            message="Do I have a saved farm in Rangpur?",
        )
    )
    assert r_b.status != "needs_memory_confirmation"
    assert len(r_b.memory.saved_farms) == 0


@pytest.mark.asyncio
async def test_memory_survives_restart(test_services: Services, tmp_path: Path):
    db_path = test_services.settings.app_db_path
    agent1 = TierZeroAgent(test_services)
    farmer_id = "farmer_restart_1"

    r1 = await agent1.turn(
        AgentTurnRequest(
            session_id="sess_r1",
            farmer_id=farmer_id,
            message="Moulovibazar, Sylhet 3 acres loam canal water BDT 150000 Rabi",
            auto_select_top_crop=True,
        )
    )
    farm_id = r1.memory.farm_id
    assert farm_id is not None

    # Re-initialize DB connection to simulate application restart
    db2 = AppDatabase(db_path)
    fresh_services = Services(
        settings=test_services.settings,
        database=db2,
        kb=test_services.kb,
        rag=test_services.rag,
        location_normalizer=test_services.location_normalizer,
        geocoder=GeoapifyClient(test_services.settings, db2, test_services.kb),
        weather=OpenMeteoClient(test_services.settings, db2),
        finance=test_services.finance,
        recommender=CropRecommender(test_services.kb, test_services.rag, test_services.finance),
        planner=SeasonPlanner(test_services.kb, test_services.rag, test_services.finance),
        memory=MemoryService(db2),
    )

    farm = fresh_services.database.get_farm(farm_id, farmer_id)
    assert farm is not None
    assert farm["profile"]["farm_size_acre"] == 3.0


@pytest.mark.asyncio
async def test_hypothetical_budget_does_not_persist(test_services: Services):
    agent = TierZeroAgent(test_services)
    farmer_id = "farmer_scen_1"

    r1 = await agent.turn(
        AgentTurnRequest(
            session_id="sess_base",
            farmer_id=farmer_id,
            message="Rangpur 2 acres loam reliable BDT 200000 Rabi",
            auto_select_top_crop=True,
        )
    )
    farm_id = r1.memory.farm_id

    # Run scenario cut query
    await agent.turn(
        AgentTurnRequest(
            session_id="sess_base",
            farmer_id=farmer_id,
            message="What if my budget is cut by 40%?",
        )
    )

    farm = test_services.database.get_farm(farm_id, farmer_id)
    assert farm["profile"]["budget_bdt"] == 200000.0


@pytest.mark.asyncio
async def test_conflicting_farm_size_is_not_silently_saved(test_services: Services):
    agent = TierZeroAgent(test_services)
    farmer_id = "farmer_conflict_1"

    r1 = await agent.turn(
        AgentTurnRequest(
            session_id="sess_c1",
            farmer_id=farmer_id,
            message="Rangpur 2 acres loam reliable BDT 200000 Rabi",
            auto_select_top_crop=True,
        )
    )
    farm_id = r1.memory.farm_id

    # Send conflicting land area (3 acres vs 2 acres)
    r2 = await agent.turn(
        AgentTurnRequest(
            session_id="sess_c2",
            farmer_id=farmer_id,
            farm_id=farm_id,
            message="Plan for my Rangpur farm with 3 acres land area",
        )
    )
    assert r2.status == "needs_memory_conflict_resolution"
    assert len(r2.memory.conflicts) > 0
    assert r2.memory.conflicts[0].field_name == "farm_size_acre"


@pytest.mark.asyncio
async def test_multiple_farms_require_selection(test_services: Services):
    agent = TierZeroAgent(test_services)
    farmer_id = "farmer_multi_1"

    # Farm 1
    await agent.turn(
        AgentTurnRequest(
            session_id="s1",
            farmer_id=farmer_id,
            message="Rangpur 2 acres loam reliable BDT 200000 Rabi",
            auto_select_top_crop=True,
        )
    )
    # Farm 2
    await agent.turn(
        AgentTurnRequest(
            session_id="s2",
            farmer_id=farmer_id,
            memory_action="create_new",
            message="Moulovibazar, Sylhet 3 acres sandy-loam canal BDT 150000 Rabi",
            auto_select_top_crop=True,
        )
    )

    farms = test_services.memory.find_candidate_farms(farmer_id, FarmProfile())
    assert len(farms) == 2


@pytest.mark.asyncio
async def test_deleting_chat_does_not_delete_farm_memory(test_services: Services):
    agent = TierZeroAgent(test_services)
    farmer_id = "farmer_del_1"

    r1 = await agent.turn(
        AgentTurnRequest(
            session_id="sess_to_delete",
            farmer_id=farmer_id,
            message="Rangpur 2 acres loam reliable BDT 200000 Rabi",
            auto_select_top_crop=True,
        )
    )
    farm_id = r1.memory.farm_id

    # Delete session chat history
    deleted = test_services.database.delete_session("sess_to_delete")
    assert deleted is True

    # Farm profile and plan versions must remain intact
    farm = test_services.database.get_farm(farm_id, farmer_id)
    assert farm is not None
    plans = test_services.database.list_plan_versions(farm_id)
    assert len(plans) == 1


@pytest.mark.asyncio
async def test_accepted_plans_are_immutable(test_services: Services):
    agent = TierZeroAgent(test_services)
    farmer_id = "farmer_immut_1"

    # Plan 1
    r1 = await agent.turn(
        AgentTurnRequest(
            session_id="sess_p1",
            farmer_id=farmer_id,
            message="Rangpur 2 acres loam reliable BDT 200000 Rabi maize",
            auto_select_top_crop=True,
        )
    )
    farm_id = r1.memory.farm_id

    # Plan 2 for same farm
    await agent.turn(
        AgentTurnRequest(
            session_id="sess_p2",
            farmer_id=farmer_id,
            farm_id=farm_id,
            memory_action="apply",
            message="Plan wheat for Rabi on my Rangpur farm",
            auto_select_top_crop=True,
        )
    )

    plans = test_services.database.list_plan_versions(farm_id)
    assert len(plans) == 2
    assert plans[0]["version_no"] == 2
    assert plans[1]["version_no"] == 1


@pytest.mark.asyncio
async def test_gemini_fallback_does_not_duplicate_messages(test_services: Services):
    engine = GeminiAgenticEngine(test_services)
    session_id = "sess_dedup_1"

    # Execute fallback turn
    await engine.run_turn(
        AgentTurnRequest(
            session_id=session_id,
            farmer_id="farmer_dedup_1",
            message="Hello AgriSense",
        )
    )

    msgs = test_services.database.list_messages(session_id)
    user_msgs = [m for m in msgs if m["role"] == "user"]
    assert len(user_msgs) == 1
