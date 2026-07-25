#!/usr/bin/env python3
"""
AgriSense AI Agentic Workflow Terminal Runner
----------------------------------------------
Runs the single-agent tool-calling agentic workflow with Gemini and real Open-Meteo weather / Geoapify integration.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.dependencies import get_services
from app.schemas import AgentTurnRequest
from app.services.gemini_agent import GeminiAgenticEngine

async def run_single_prompt(prompt: str, session_id: str = None):
    print("=" * 80)
    print(f"User Prompt: {prompt}")
    print("=" * 80)

    services = get_services()
    engine = GeminiAgenticEngine(services)

    req = AgentTurnRequest(message=prompt, session_id=session_id)
    response = await engine.run_turn(req)

    print("\n" + "=" * 80)
    print("AGENT REPLY:")
    print("=" * 80)
    print(response.message)

    print("\n" + "=" * 80)
    print("EXTRACTED FARM PROFILE STATE:")
    print("=" * 80)
    print(json.dumps(response.profile.model_dump(mode="json"), indent=2))

    print("\n" + "=" * 80)
    print(f"OPERATIONAL TOOL TRACES ({len(response.trace)} calls recorded):")
    print("=" * 80)
    for idx, trace in enumerate(response.trace, 1):
        tool_name = getattr(trace, "tool_name", getattr(trace, "tool", "unknown"))
        duration = getattr(trace, "duration_ms", 0.0)
        source = getattr(trace, "source_kind", "direct")
        params = getattr(trace, "parameters", {})
        print(f"\n[Trace #{idx}] Tool: {tool_name} ({duration:.1f}ms) | Source: {source}")
        print(f"  - Parameters: {json.dumps(params)}")

    print("\n" + "=" * 80)
    print(f"STATUS: {response.status} | Missing Fields: {response.missing_fields}")
    print("=" * 80)
    return response.session_id

async def interactive_mode():
    print("\n" + "🌱 " * 20)
    print("   AGRISENSE AI - AGENTIC TOOL CALLING WORKFLOW")
    print("🌱 " * 20 + "\n")
    print("Type 'exit' to quit.\n")

    session_id = None
    while True:
        try:
            prompt = input("\nFarmer > ").strip()
            if not prompt:
                continue
            if prompt.lower() in ("exit", "quit", "q"):
                print("Goodbye!")
                break
            session_id = await run_single_prompt(prompt, session_id=session_id)
        except (KeyboardInterrupt, EOFError):
            print("\nExiting interactive mode.")
            break

def main():
    if len(sys.argv) > 1:
        prompt = " ".join(sys.argv[1:])
        asyncio.run(run_single_prompt(prompt))
    else:
        asyncio.run(interactive_mode())

if __name__ == "__main__":
    main()
