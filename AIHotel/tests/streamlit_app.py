"""
Travel Assistant - Streamlit Chat Interface

Real-time chat interface with intelligent routing:
- Normal chat (greetings, small talk)
- Travel information (destinations, tips)
- Hotel search (recommendations with filters)
"""
import streamlit as st
import asyncio
from typing import Dict, Any, List
from datetime import datetime
import threading

# Import from main.py
from main import (
    initialize_system,
    run_travel_chat,
    get_database_statistics
)

# Page configuration
st.set_page_config(
    page_title="Travel Assistant",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .stChatMessage {
        padding: 1rem;
        border-radius: 0.5rem;
    }
    .hotel-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
        border-left: 4px solid #1f77b4;
    }
    .hotel-name {
        font-size: 1.2rem;
        font-weight: bold;
        color: #1f77b4;
    }
    .hotel-rating {
        color: #ffa500;
        font-weight: bold;
    }
    .filter-badge {
        background-color: #e1f5ff;
        padding: 0.2rem 0.5rem;
        border-radius: 0.3rem;
        margin: 0.2rem;
        display: inline-block;
        font-size: 0.85rem;
    }
</style>
""", unsafe_allow_html=True)


def initialize_session_state():
    """Initialize Streamlit session state variables."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    if "shown_hotel_ids" not in st.session_state:
        st.session_state.shown_hotel_ids = []
    
    if "history" not in st.session_state:
        st.session_state.history = []
    
    if "system_initialized" not in st.session_state:
        st.session_state.system_initialized = False
    
    if "hotel_count" not in st.session_state:
        st.session_state.hotel_count = 0


def format_hotel_card(hotel: Dict[str, Any], index: int) -> str:
    """Format a hotel as an HTML card."""
    name = hotel.get('hotel_name', 'Unknown Hotel')
    city = hotel.get('city', 'Unknown').title()
    rating = hotel.get('average_rating', 0.0)
    total_ratings = hotel.get('total_ratings', 0)
    price = hotel.get('price', 'N/A')
    score = hotel.get('composite_score', 0.0)
    
    # Build amenities display
    amenities = hotel.get('amenities', '')
    if isinstance(amenities, str) and amenities:
        amenities_list = [a.strip() for a in amenities.split(',')[:5]]  # Show first 5
        amenities_html = ' '.join([f'<span style="background-color: #e8f4f8; padding: 0.2rem 0.5rem; border-radius: 0.3rem; margin: 0.1rem; font-size: 0.8rem;">🏷️ {a}</span>' for a in amenities_list])
    else:
        amenities_html = ''
    
    # Special offers
    special_offers = hotel.get('special_offers', [])
    offers_html = ''
    if special_offers:
        offers_html = '<br>'.join([f'<span style="color: #28a745; font-size: 0.9rem;">🎁 {offer}</span>' for offer in special_offers])
    
    return f"""
    <div class="hotel-card">
        <div class="hotel-name">#{index}. {name}</div>
        <div style="margin: 0.5rem 0;">
            <span style="color: #666;">📍 {city}</span> • 
            <span class="hotel-rating">⭐ {rating:.2f}/5.0</span> 
            <span style="color: #888;">({total_ratings} reviews)</span>
        </div>
        <div style="margin: 0.5rem 0;">
            <strong>Price:</strong> ${price} • 
            <strong>Match Score:</strong> {score:.3f}
        </div>
        {f'<div style="margin: 0.5rem 0;">{amenities_html}</div>' if amenities_html else ''}
        {f'<div style="margin: 0.5rem 0;">{offers_html}</div>' if offers_html else ''}
    </div>
    """


def display_filters(metadata: Dict[str, Any]):
    """Display applied filters in the sidebar or main area."""
    filters_applied = metadata.get('filters_applied', {})
    
    if not filters_applied or not any(filters_applied.values()):
        return
    
    st.markdown("**🔍 Applied Filters:**")
    
    filter_items = []
    if filters_applied.get('city'):
        filter_items.append(f"📍 City: {filters_applied['city']}")
    if filters_applied.get('min_rating'):
        filter_items.append(f"⭐ Min Rating: {filters_applied['min_rating']}")
    if filters_applied.get('max_rating'):
        filter_items.append(f"⭐ Max Rating: < {filters_applied['max_rating']}")
    if filters_applied.get('price_max'):
        filter_items.append(f"💰 Max Price: ${filters_applied['price_max']}")
    if filters_applied.get('amenities'):
        filter_items.append(f"🏷️ Amenities: {', '.join(filters_applied['amenities'])}")
    
    for item in filter_items:
        st.markdown(f'<span class="filter-badge">{item}</span>', unsafe_allow_html=True)


def _run_async(coro):
    """
    Run async coroutine synchronously in Streamlit.
    
    This creates a new event loop in the current thread if needed,
    avoiding conflicts with Streamlit's event loop.
    """
    try:
        # Try to get the current event loop
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If loop is running, we need to create a new one in a thread
            import nest_asyncio
            nest_asyncio.apply()
            return loop.run_until_complete(coro)
        else:
            # Loop exists but not running, use it
            return loop.run_until_complete(coro)
    except RuntimeError:
        # No event loop, create new one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            # Don't close the loop, keep it for reuse
            pass


def process_message(user_input: str):
    """Process user message and get response (sync wrapper for async code)."""
    # Add user message to chat
    st.session_state.messages.append({
        "role": "user",
        "content": user_input,
        "timestamp": datetime.now()
    })
    
    # Show processing indicator
    with st.spinner("🤔 Thinking..."):
        # Call the agent
        result = _run_async(run_travel_chat(
            query=user_input,
            history=st.session_state.history,
            shown_hotel_ids=st.session_state.shown_hotel_ids
        ))
    
    # Update session state
    st.session_state.shown_hotel_ids = result.get('shown_hotel_ids', st.session_state.shown_hotel_ids)
    st.session_state.history.append({"role": "user", "content": user_input})
    st.session_state.history.append({"role": "assistant", "content": result['natural_language_response']})
    
    # Add assistant response to chat
    st.session_state.messages.append({
        "role": "assistant",
        "content": result['natural_language_response'],
        "hotels": result.get('recommended_hotels', []),
        "metadata": result.get('metadata', {}),
        "timestamp": datetime.now()
    })


def main():
    """Main Streamlit app."""
    # Initialize session state
    initialize_session_state()
    
    # Sidebar
    with st.sidebar:
        st.title("🌍 Travel Assistant")
        st.markdown("---")
        
        st.info("**I can help with:**\n- 🗣️ Casual chat\n- 🌍 Travel info\n- 🏨 Hotel search")
        st.markdown("---")
        
        # System status
        st.subheader("System Status")
        
        # Initialize system button
        if not st.session_state.system_initialized:
            if st.button("🚀 Initialize System", use_container_width=True):
                with st.spinner("Initializing database..."):
                    # Run async initialization
                    _run_async(initialize_system())
                    st.session_state.system_initialized = True
                    stats = _run_async(get_database_statistics())
                    st.session_state.hotel_count = stats.get('total_hotels', 0)
                    st.success("✅ System initialized!")
                    st.rerun()
        else:
            st.success("✅ System Ready")
            st.metric("Hotels in Database", st.session_state.hotel_count)
        
        st.markdown("---")
        
        # Actions
        st.subheader("Actions")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🔄 Refresh Stats", use_container_width=True, disabled=not st.session_state.system_initialized):
                with st.spinner("Fetching stats..."):
                    stats = _run_async(get_database_statistics())
                    st.session_state.hotel_count = stats.get('total_hotels', 0)
                    st.success(f"✅ {stats['total_hotels']} hotels available")
                    st.rerun()
        
        with col2:
            if st.button("🗑️ Reset Chat", use_container_width=True):
                st.session_state.messages = []
                st.session_state.shown_hotel_ids = []
                st.session_state.history = []
                st.success("✅ Chat reset!")
                st.rerun()
        
        st.markdown("---")
        
        # Session info
        st.subheader("Session Info")
        st.metric("Messages", len(st.session_state.messages))
        st.metric("Hotels Shown", len(st.session_state.shown_hotel_ids))
        
        st.markdown("---")
        
        # Example queries
        st.subheader("💡 Try These")
        
        st.markdown("**🗣️ Normal Chat**")
        normal_examples = ["Hello!", "Thank you", "How are you?"]
        for ex in normal_examples:
            if st.button(f"💬 {ex}", key=f"ex_{ex}", use_container_width=True):
                st.session_state.user_input = ex
                st.rerun()
        
        st.markdown("**🌍 Travel Info**")
        travel_examples = [
            "Best time to visit Paris?",
            "Things to do in Tokyo",
            "Travel tips for Europe"
        ]
        for ex in travel_examples:
            if st.button(f"🗺️ {ex}", key=f"ex_{ex}", use_container_width=True):
                st.session_state.user_input = ex
                st.rerun()
        
        st.markdown("**🏨 Hotel Search**")
        hotel_examples = [
            "Hotels with rating > 4.5",
            "Luxury hotels with spa",
            "Hotels with pool in New York"
        ]
        for ex in hotel_examples:
            if st.button(f"🏨 {ex}", key=f"ex_{ex}", use_container_width=True):
                st.session_state.user_input = ex
                st.rerun()
    
    # Main content
    st.title("� Travel Assistant")
    st.markdown("Ask me anything - casual chat, travel tips, or hotel recommendations!")
    
    # Display chat messages
    chat_container = st.container()
    
    with chat_container:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
                
                # Display query type badge for assistant messages
                if message["role"] == "assistant" and "metadata" in message:
                    query_type = message.get("metadata", {}).get("query_type", "")
                    if query_type:
                        type_emoji = {
                            "normal_chat": "🗣️",
                            "travel_info": "🌍",
                            "hotel_search": "🏨"
                        }
                        emoji = type_emoji.get(query_type, "💬")
                        type_label = query_type.replace("_", " ").title()
                        st.caption(f"{emoji} {type_label}")
                
                # Display hotels if present
                if message["role"] == "assistant" and "hotels" in message:
                    hotels = message["hotels"]
                    metadata = message.get("metadata", {})
                    
                    if hotels:
                        st.markdown("---")
                        
                        # Display filters
                        display_filters(metadata)
                        
                        st.markdown("### 🏨 Recommended Hotels")
                        
                        # Display each hotel
                        for idx, hotel in enumerate(hotels, 1):
                            st.markdown(format_hotel_card(hotel, idx), unsafe_allow_html=True)
                        
                        # Session stats
                        total_shown = metadata.get('total_shown_in_session', 0)
                        if total_shown > 0:
                            st.info(f"💡 **Session:** Shown {total_shown} unique hotels so far")
    
    # Chat input
    if st.session_state.system_initialized:
        # Check if example was clicked
        if "user_input" in st.session_state and st.session_state.user_input:
            user_input = st.session_state.user_input
            st.session_state.user_input = None
            process_message(user_input)
            st.rerun()
        
        # Regular chat input
        if prompt := st.chat_input("Ask about travel or hotels..."):
            process_message(prompt)
            st.rerun()
    else:
        st.warning("⚠️ Please initialize the system from the sidebar first.")
        st.info("💡 Click **'🚀 Initialize System'** in the sidebar to start")


if __name__ == "__main__":
    main()
