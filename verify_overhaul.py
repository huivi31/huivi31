
import sys
import os
import json
import time

# Add current directory to path
sys.path.append(os.getcwd())
sys.path.append("/tmp/huivi31_repo")

from agents import SYSTEM_STATE, PERSONA_INDEX, ATTACK_TECHNIQUES, EVENT_BUS
from battle import run_red_team_planning, run_collaborative_attack, run_agent_discussion, OPENCLAW_BOARD

def verify_structure():
    print("=== 1. Verifying Structure ===")
    print(f"Total Agents: {len(PERSONA_INDEX)}")
    if len(PERSONA_INDEX) < 50:
        print("X Warning: Expected ~56 agents, found fewer.")
    else:
        print("✓ Agent count looks correct.")
        
    print(f"Technique Categories: {len(ATTACK_TECHNIQUES)}")
    categories = list(ATTACK_TECHNIQUES.keys())
    print(f"Categories: {categories}")
    expected_cats = ["情感操纵", "身份伪装", "时序与热点", "认知战术"]
    missing = [c for c in expected_cats if c not in categories]
    if missing:
        print(f"X Missing categories: {missing}")
    else:
        print("✓ All new categories present.")

def verify_collaboration():
    print("\n=== 2. Verifying Collaboration (OpenClaw Board) ===")
    
    topic = "测试话题_言论审查"
    print(f"Running Red Team Planning for topic: {topic}...")
    
    try:
        planning_result = run_red_team_planning(topic)
        print("✓ Planning meeting finished.")
        print(f"  Proposals: {planning_result.get('proposals_count')}")
        print(f"  Winner: {planning_result.get('winner', {}).get('strategy_name', 'None')}")
        
        # Check Board content
        plans = OPENCLAW_BOARD.active_plans.get(topic, [])
        print(f"  Board Plans: {len(plans)}")
        if len(plans) > 0:
            print("✓ Plans successfully submitted to Board.")
        else:
            print("X No plans found on Board.")
            
    except Exception as e:
        print(f"X Planning failed: {str(e)}")
        import traceback
        traceback.print_exc()

def verify_attack():
    print("\n=== 3. Verifying Collaborative Attack ===")
    
    # Pick some agents
    agent_ids = list(PERSONA_INDEX.keys())[:3]
    topic = "测试话题_敏感词"
    
    try:
        # Pre-seed capability score to avoid 0 capability
        for pid in agent_ids:
             SYSTEM_STATE["peripheral_agents"][pid]["capability_score"] = 5.0

        attack_result = run_collaborative_attack(agent_ids, topic)
        print("✓ Collaborative attack finished.")
        print(f"  Board Intel Used: {attack_result.get('board_intel_used')}")
        print(f"  Individual Results: {len(attack_result.get('individual_results', []))}")
        
        # Check if intel was posted
        intel = OPENCLAW_BOARD.intel_feed
        print(f"  Total Intel Posts: {len(intel)}")
        
    except Exception as e:
        print(f"X Attack failed: {str(e)}")
        import traceback
        traceback.print_exc()

def verify_discussion():
    print("\n=== 4. Verifying Discussion Board ===")
    agent_ids = list(PERSONA_INDEX.keys())[:3]
    topic = "讨论_如何绕过"
    
    try:
        discussions = run_agent_discussion(agent_ids, topic)
        print("✓ Discussion finished.")
        print(f"  Posts: {len(discussions)}")
        
        # Check events
        events = EVENT_BUS.get_recent(10)
        print(f"  Recent Events: {len(events)}")
        
    except Exception as e:
        print(f"X Discussion failed: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    verify_structure()
    verify_collaboration()
    verify_attack()
    verify_discussion()
