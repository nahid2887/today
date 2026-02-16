# Hotel Recommendation Agent

An intelligent hotel recommendation system built with LangGraph, LangChain, ChromaDB, and Groq (Llama 3).

## Architecture

This system implements an **Agentic RAG (Retrieval-Augmented Generation)** workflow with three distinct stages:

1. **Search Node**: Performs hybrid search combining city filtering with semantic vector search
2. **Rank Node**: Scores hotels using weighted formula: `Score = (0.6 × rating) + (0.4 × similarity)`
3. **Hydrate Node**: Fetches real-time pricing and offers from live API endpoints

## Project Structure

```
AIHotel/
├── config/
│   ├── __init__.py
│   └── settings.py          # Configuration and environment variables
├── core/
│   ├── __init__.py
│   └── vector_store.py      # VectorManager for ChromaDB operations
├── tools/
│   ├── __init__.py
│   └── hotel_tools.py       # Live data fetching tools
├── agents/
│   ├── __init__.py
│   └── hotel_agent.py       # LangGraph state machine orchestration
├── data/
│   └── chroma_db/           # Persistent vector storage (auto-created)
├── main.py                  # Main entry point
├── pyproject.toml          # Dependencies
├── .env                     # Environment variables (create this)
└── README.md
```

## Installation

### Prerequisites

- Python 3.10+
- Groq API Key (get from https://console.groq.com)

### Setup

1. **Clone or navigate to the project**:
```bash
cd /home/robin/Downloads/AIHotel
```

2. **Create virtual environment**:
```bash
python -m venv .venv
source .venv/bin/activate  # On Linux/Mac
```

3. **Install dependencies**:
```bash
pip install -e .
```

4. **Create `.env` file**:
```bash
cat > .env << EOL
GROQ_API_KEY=your_groq_api_key_here
EOL
```

## Usage

### As a Python Module (Recommended for Backend Integration)

```python
import asyncio
from main import run_travel_chat, sync_hotel_data

async def example():
    # First time: Sync hotel data
    await sync_hotel_data()
    
    # Make a recommendation
    result = await run_travel_chat(
        query="Find me a highly rated hotel in Bangalore with good amenities",
        history=[]
    )
    
    print(result['natural_language_response'])
    for hotel in result['recommended_hotels']:
        print(f"- {hotel['hotel_name']}: ${hotel['price']}")

asyncio.run(example())
```

### FastAPI Integration Example

```python
from fastapi import FastAPI
from main import run_travel_chat, initialize_system, sync_hotel_data

app = FastAPI()

@app.on_event("startup")
async def startup():
    initialize_system()
    await sync_hotel_data()  # Sync on startup

@app.post("/api/recommend")
async def recommend(query: str):
    result = await run_travel_chat(query)
    return result
```

### Interactive CLI Mode

```bash
python main.py
```

This starts an interactive session where you can:
- Type queries naturally: `"Find luxury hotels in Bangalore"`
- Type `sync` to refresh hotel data
- Type `quit` to exit

## API Endpoints

The system connects to:

- **Sync Endpoint**: `http://10.10.13.27:8000/api/hotel/sync/`
  - Fetches all hotels for ChromaDB indexing
  
- **Details Endpoint**: `http://10.10.13.27:8000/api/hotel/ai/details/{id}/`
  - Fetches live pricing and special offers

## Key Features

### 1. Hybrid Search
- **City Filtering**: Exact match on city metadata
- **Semantic Search**: Vector similarity on hotel descriptions and amenities

### 2. Intelligent Ranking
Hotels are scored using:
```
Score = (0.6 × normalized_rating) + (0.4 × semantic_similarity)
```

This ensures that:
- High-rated hotels (e.g., 4.70/5) are prioritized over lower-rated ones (e.g., 3.53/5)
- Semantic relevance to the query is also considered

### 3. Live Data Hydration
Top 3 ranked hotels are enriched with:
- Current pricing
- Special offers and discounts
- Real-time availability
- Latest amenity information

### 4. Closed Database Protocol
The agent **only recommends hotels in ChromaDB**. No external web searches are performed, ensuring controlled, verified recommendations.

## Embedding Strategy

Each hotel is embedded using this format:
```
"Hotel: {name} in {city}. {description}. Features: {amenities}"
```

Metadata stored:
- `id`: Hotel unique identifier
- `city`: City name (lowercase for filtering)
- `average_rating`: Rating score
- `total_ratings`: Number of reviews

## Configuration

Edit [`config/settings.py`](config/settings.py) to customize:

- **LLM Model**: Change `GROQ_MODEL` (default: `llama3-70b-8192`)
- **Ranking Weights**: Adjust `RATING_WEIGHT` and `SIMILARITY_WEIGHT`
- **Top K Results**: Modify `TOP_K_RESULTS` (default: 3)
- **Embedding Model**: Change `EMBEDDING_MODEL`

## Maintenance

### Refresh Hotel Data

```python
from main import sync_hotel_data
import asyncio

asyncio.run(sync_hotel_data())
```

Run this:
- Daily via cron job
- When hotel inventory changes
- Before deploying updates

### Check Database Status

```python
from main import get_hotel_count
import asyncio

count = asyncio.run(get_hotel_count())
print(f"Hotels indexed: {count}")
```

## Troubleshooting

### No hotels found
```bash
python -c "import asyncio; from main import sync_hotel_data; asyncio.run(sync_hotel_data())"
```

### API connection errors
- Verify the backend API is running on `http://10.10.13.27:8000`
- Check network connectivity
- Review logs in console output

### Groq API errors
- Verify `GROQ_API_KEY` in `.env`
- Check API quota at https://console.groq.com

## Example Queries

- `"Find me a luxury hotel in Bangalore"`
- `"I need a highly rated hotel with a pool"`
- `"Show me budget-friendly options in Mumbai"`
- `"Hotels with spa and WiFi in the tech park area"`

## Development

### Adding New Features

1. **Custom Ranking**: Modify `_rank_node()` in [`agents/hotel_agent.py`](agents/hotel_agent.py)
2. **New Filters**: Extend `search_hotels()` in [`core/vector_store.py`](core/vector_store.py)
3. **Additional API Calls**: Add tools in [`tools/hotel_tools.py`](tools/hotel_tools.py)

### Testing

```python
# Test vector search
from core import VectorManager
import asyncio

async def test():
    vm = VectorManager()
    await vm.sync_hotels()
    results = vm.search_hotels("luxury hotel", city="bangalore", k=5)
    print(results)

asyncio.run(test())
```

## License

Proprietary - Internal Use Only

## Support

For issues or questions, contact the AI Engineering team.
