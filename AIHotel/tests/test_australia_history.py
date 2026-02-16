import asyncio
import json
import time
from typing import List, Dict, Any
from main import initialize_system, run_travel_chat

SCENARIOS = [
    {
        "name": "Sydney Location Follow-up",
        "steps": [
            "Find me hotels in Sydney",
            "Which of those are near Circular Quay?",
            "Do any of them have a pool?"
        ]
    },
    {
        "name": "Melbourne Price Negotiation",
        "steps": [
            "I'm looking for luxury hotels in Melbourne",
            "Actually, show me something under $200 instead",
            "Which ones are the best rated of those?"
        ]
    },
    {
        "name": "Brisbane Amenity Drill-down",
        "steps": [
            "Hotels in Brisbane for a family",
            "Do they have free breakfast?",
            "I also need parking for a large van"
        ]
    }
]

async def run_history_audit():
    print("\n" + "="*80)
    print("🧠 AUSTRALIAN HISTORY AUDIT: CONTEXT & FOLLOW-UPS")
    print("="*80)
    
    await initialize_system()
    
    for scenario in SCENARIOS:
        print(f"\n▶ SCENARIO: {scenario['name']}")
        print("=" * 40)
        
        history = []
        shown_ids = []
        last_hotels = []
        
        for i, step in enumerate(scenario['steps'], 1):
            print(f"\n[TURN {i}]: {step}")
            
            start_time = time.time()
            result = await run_travel_chat(
                step, 
                history=history, 
                shown_hotel_ids=shown_ids,
                last_hotels=last_hotels
            )
            duration = time.time() - start_time
            
            # Update local state for next turn
            history.append({"role": "user", "content": step})
            history.append({"role": "assistant", "content": result.get('natural_language_response', '')})
            
            hotels = result.get('recommended_hotels', [])
            last_hotels = result.get('last_hotels', [])
            current_ids = [h['id'] for h in hotels]
            shown_ids.extend(current_ids)
            
            print(f"[BOT]: {result.get('natural_language_response', 'NO RESPONSE')}")
            print(f"[DATA]: Found {len(hotels)} hotels. IDs: {current_ids}")
            
            # Analyze context awareness
            if i > 1:
                # Basic check: Did the bot use words like "those", "them", "these", "still", "also"?
                context_words = ["those", "them", "these", "still", "also", "previously", "mentioned", "earlier"]
                uses_context = any(w in result.get('natural_language_response', '').lower() for w in context_words)
                if uses_context:
                    print(f"✅ Context Check: Bot appears to be referencing previous turn.")
                else:
                    print(f"⚠️ Context Check: Bot response might be too generic/standalone.")

            await asyncio.sleep(0.5)

    print("\n" + "="*80)
    print("📊 HISTORY AUDIT COMPLETED")
    print("="*80 + "\n")

if __name__ == "__main__":
    asyncio.run(run_history_audit())
