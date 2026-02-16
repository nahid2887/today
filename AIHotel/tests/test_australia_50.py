import asyncio
import json
import time
import re
from typing import List, Dict, Any
from main import initialize_system, run_travel_chat

# EXTENDED AUSTRALIAN TEST CASES (PLACE, PRICE, AMENITY, FAMILY, ROOMS, DISCOUNTS)
AUSTRALIAN_HYPER_TEST_CASES = [
    # --- OCCUPANCY & FAMILY SIZE ---
    "Family of 5 looking for a hotel in Sydney with pool",
    "Room for 2 adults and 3 children in Melbourne",
    "Hotel in Brisbane for a large family",
    "Need a place for 4 adults in Perth",
    "Small apartment style hotel in Adelaide for 2 people",
    "Traveling with kids to Hobart, need a family suite",
    "Best Cairns hotel for a honeymoon couple",
    "Group of 6 friends looking for a hotel in Gold Coast",
    "Quiet room for a solo business traveler in Sydney",
    "Senior couple looking for a comfortable stay in Melbourne",

    # --- ROOM NUMBERS ---
    "I need 2 rooms in Sydney near Circular Quay",
    "Looking for 3 separate rooms in Brisbane for a work trip",
    "Can I book 5 rooms in Perth for a wedding party?",
    "Need a hotel with connecting rooms in Adelaide",
    "Looking for 2 luxury suites in Melbourne",
    "Do you have a hotel in Hobart with 4 available rooms?",
    "Searching for a block of 3 rooms in Cairns",
    "Single room and a double room in Surfers Paradise",
    "Connecting family rooms in Newcastle",
    "Multiple rooms for a group in Pokolbin",

    # --- PRICE RANGES (ADVANCED) ---
    "Luxury hotels in Sydney over $400 a night",
    "Affordable stays in Melbourne between $100 and $200",
    "Cheapest possible hotel in Brisbane for under $80",
    "High-end resort in Perth with prices around $500",
    "Budget motels in Adelaide under $120",
    "Mid-range hotels in Hobart $150 to $250",
    "Cairns hotels for exactly $200 per night",
    "Most expensive presidential suite in Sydney",
    "Cheap backpacker style in Gold Coast",
    "Value for money hotels in Newcastle under $140",

    # --- DISCOUNTS & OFFERS ---
    "Are there any hotels with discounts in Sydney right now?",
    "Find me a hotel in Melbourne with a special offer",
    "Looking for 'Last Minute' deals in Brisbane",
    "Any promo codes or discounted rates in Perth?",
    "Hotels in Adelaide with a 'Stay 3 Pay 2' type of deal",
    "Best price guarantee hotels in Hobart",
    "Cairns hotels with early bird discounts",
    "Find a hotel in Sydney with free breakfast and 20% off",
    "Deals for Surfers Paradise with free parking",
    "Discounted luxury in Melbourne",

    # --- MULTI-AMENITY & COMPLEX ---
    "Sydney hotel with a pool, gym, AND free wifi",
    "Melbourne stay with spa, sauna, and room service",
    "Brisbane hotel near the airport with a shuttle",
    "Perth hotel with a balcony and ocean view",
    "Adelaide hotel with an electric vehicle charger",
    "Hobart hotel that is pet friendly and has a fireplace",
    "Cairns resort with a swim-up bar and reef tours",
    "Sydney hotel with 24-hour check-in and luggage storage",
    "Melbourne hotel with a rooftop bar and live music",
    "Gold Coast hotel with a private beach access"
]

def analyze_response_quality(query: str, result: Dict[str, Any]):
    """Analyzes the response for common requirements mentioned in the query."""
    nl = result.get('natural_language_response', "").lower()
    hotels = result.get('recommended_hotels', [])
    
    analysis = []
    
    # Check Price Logic
    price_match = re.search(r'\$(\d+)', query)
    if price_match:
        target_price = int(price_match.group(1))
        found_prices = [h.get('base_price_per_night', 0) for h in hotels]
        if "under" in query.lower() or "less than" in query.lower():
            if any(p > target_price + 20 for p in found_prices): # Allowance for relaxation
                analysis.append(f"⚠️ Price might exceed 'under ${target_price}' constraint.")
        elif "over" in query.lower() or "more than" in query.lower():
             if any(p < target_price - 20 for p in found_prices):
                analysis.append(f"⚠️ Price might be below 'over ${target_price}' constraint.")

    # Check Amenities
    amenities_to_check = ["pool", "gym", "wifi", "parking", "spa", "pet", "breakfast"]
    for amenity in amenities_to_check:
        if amenity in query.lower():
            included = any(amenity in str(h.get('amenities', [])).lower() for h in hotels)
            if not included and len(hotels) > 0:
                if "unfortunately" in nl or "don't have" in nl or "missing" in nl or "no " in nl:
                    analysis.append(f"✅ Correctly admitted missing amenity: {amenity}")
                else:
                    analysis.append(f"❓ Query asked for {amenity}, but results might lack it (Check honesty).")

    # Check Occupancy/Rooms
    occupancy_keywords = ["family", "adults", "kids", "people", "rooms", "suite", "room"]
    if any(k in query.lower() for k in occupancy_keywords):
        if any(k in nl for k in occupancy_keywords):
            analysis.append("✅ Agent acknowledged occupancy/room requirements in conversation.")
        else:
            analysis.append("⚠️ Agent might have ignored room count or family size in text.")

    # Check Discounts
    discount_keywords = ["discount", "offer", "deal", "promo", "off", "bargain"]
    if any(k in query.lower() for k in discount_keywords):
        has_badges = any(len(h.get('badges', [])) > 0 for h in hotels)
        if has_badges:
            analysis.append("✅ Agent found hotels with specific discount badges.")
        else:
            analysis.append("⚠️ No discount badges found in results for discount-related query.")

    return analysis

async def run_australian_hyper_audit():
    print("\n" + "="*80)
    print("🦘 AUSTRALIAN HYPER-AUDIT: 50 COMPLEX SCENARIOS")
    print("="*80)
    
    await initialize_system()
    
    passed = 0
    total = len(AUSTRALIAN_HYPER_TEST_CASES)
    
    for i, query in enumerate(AUSTRALIAN_HYPER_TEST_CASES, 1):
        print(f"\nTEST #{i}: {query}")
        print("-" * 40)
        
        try:
            start_time = time.time()
            result = await run_travel_chat(query, history=[], shown_hotel_ids=[])
            duration = time.time() - start_time
            
            # 1. Bot Reply
            print(f"[BOT RESPONSE]:\n{result.get('natural_language_response', 'NO RESPONSE')}")
            
            # 2. FULL JSON DATA FOR DEBUGGING
            print("\n[FULL JSON DATA]:")
            print(json.dumps(result.get('recommended_hotels', []), indent=2))
            
            # 3. Automated Heuristic Analysis
            analysis = analyze_response_quality(query, result)
            if analysis:
                print("\n[AUDIT ANALYSIS]:")
                for item in analysis:
                    print(f"  {item}")
            
            # 4. Data Check
            hotels = result.get('recommended_hotels', [])
            print(f"\n[DATA SUMMARY]: Found {len(hotels)} hotels. Execution: {duration:.2f}s")
            
            if len(hotels) > 0:
                # Print first hotel brief for sanity check
                h = hotels[0]
                print(f"  - Top Result: {h['hotel_name']} (${h['base_price_per_night']})")
                if h.get('badges'): print(f"  - Badges: {h['badges']}")
            
            # Basic pass criteria
            if len(hotels) > 0 or "snag" in result.get('natural_language_response', "").lower():
                passed += 1
                
        except Exception as e:
            print(f"[CRITICAL ERROR]: {e}")
            
        await asyncio.sleep(0.1)

    print("\n" + "="*80)
    print("📊 HYPER-AUDIT COMPLETED")
    print("="*80)
    print(f"Total Australian Challenges: {total}")
    print(f"Operational Success: {passed}/{total}")
    print(f"Success Rate: {(passed/total)*100:.1f}%")
    print("="*80 + "\n")

if __name__ == "__main__":
    asyncio.run(run_australian_hyper_audit())
