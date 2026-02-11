# AI Integration API Documentation

## Overview
Two specialized API endpoints for AI/RAG system integration that provide hotel data for embeddings and real-time verification.

---

## 1. Bulk Sync Endpoint (RAG System Data)

### Endpoint
```
GET /api/hotel/sync/
```

### Purpose
Provides all static hotel information needed for RAG embeddings and AI training. Designed for batch processing with incremental sync support.

### Authentication
**None required** - Open to AI system (no API key needed for this MVP)

### Query Parameters
- `since` (optional): ISO 8601 datetime string for incremental syncs
  - Example: `?since=2026-02-09T00:00:00Z`
  - Returns only hotels updated after this timestamp

### Response Format
```json
{
  "message": "Synced 20 approved hotels",
  "count": 20,
  "hotels": [
    {
      "id": 2,
      "partner_name": "partner_1",
      "hotel_name": "Grand Plaza Hotel",
      "description": "Luxury 5-star hotel...",
      "location": "123 Main St, Downtown",
      "city": "New York",
      "country": "USA",
      "amenities": ["Free WiFi", "Pool", "Gym", "Restaurant", "Bar", "Spa"],
      "images": [],
      "room_type": "suite",
      "number_of_rooms": 150,
      "average_rating": "3.53",
      "total_ratings": 437,
      "last_updated": "2026-02-09T08:25:46.098126+00:00"
    }
    // ... 19 more hotels
  ]
}
```

### Data Fields Explained
- **id**: Unique hotel identifier (use for real-time lookups)
- **hotel_name**: Name for display/context
- **description**: Full text for embeddings
- **location, city, country**: Geographic data for filtering
- **amenities**: Array of features for RAG context
- **average_rating, total_ratings**: Quality indicators
- **last_updated**: Timestamp for incremental sync detection

### Use Cases
1. **Initial RAG Training**: Fetch all 20 hotels to build embeddings
2. **Incremental Updates**: Query with `since=<last_sync_time>` to update only changed hotels
3. **Scheduled Sync**: Set up cron job to run every 6 hours
   ```bash
   curl "http://localhost:8000/api/hotel/sync/?since=$(date -u -d '6 hours ago' '+%Y-%m-%dT%H:%M:%SZ')"
   ```

---

## 2. Real-Time Detail Endpoint (AI Verification)

### Endpoint
```
GET /api/hotel/ai/details/<hotel_id>/
```

### Purpose
Returns volatile, real-time data that changes frequently. Called by AI during chat to verify hotel details before recommending.

### Authentication
**None required** - Open to AI system

### Path Parameters
- `hotel_id` (required): Hotel ID from bulk sync endpoint
  - Example: `GET /api/hotel/ai/details/2/`

### Response Format
```json
{
  "message": "Hotel details retrieved successfully",
  "hotel": {
    "id": 2,
    "partner_name": "partner_1",
    "hotel_name": "Grand Plaza Hotel",
    "base_price_per_night": "250.00",
    "commission_rate": "2.96",
    "active_special_offers": [
      {
        "discount_percentage": 25.0,
        "special_perks": ["Free fitness center", "Free coffee"],
        "valid_until": "2026-03-13"
      },
      {
        "discount_percentage": 15.0,
        "special_perks": ["Free breakfast", "Late checkout"],
        "valid_until": "2026-07-28"
      }
    ],
    "is_approved": "approved",
    "updated_at": "2026-02-09T08:25:46.098126Z"
  }
}
```

### Data Fields Explained
- **base_price_per_night**: Current price (can change via partner updates)
- **commission_rate**: Partner commission percentage
- **active_special_offers**: Currently active promotions with:
  - `discount_percentage`: Discount amount
  - `special_perks`: Additional benefits
  - `valid_until`: Expiration date (only future dates included)
- **is_approved**: Always "approved" (only approved hotels returned)
- **updated_at**: Last modification timestamp

### Use Cases
1. **Verify Before Recommend**: Before suggesting a hotel to user, call this endpoint
   ```javascript
   // In AI chat flow
   hotel_details = fetch(`/api/hotel/ai/details/${hotel_id}/`)
   if hotel_details.base_price_per_night < user_budget:
       recommend_to_user()
   ```

2. **Check Current Offers**: Get latest promotions for display
3. **Verify Hotel Status**: Ensure hotel is still approved before recommending

### Error Responses
```json
{
  "error": "Hotel not found or not approved",
  "hotel_id": 99
}
```
Status: `404 Not Found`

---

## Test Data

### Pre-loaded Hotels
✅ 20 approved hotels with complete data
- Real hotel names and locations
- Varied prices: $110 - $300 per night
- Different room types: standard, deluxe, suite, presidential
- 1-3 active special offers per hotel
- Ratings between 3.5 - 5.0 stars

### Partner Accounts
✅ 20 partner accounts (one per hotel)
- Username: `partner_1` to `partner_20`
- Password: `testpass123`
- Each has an associated hotel with `is_approved: "approved"`

### Test Queries

**Get all hotels for RAG:**
```bash
curl "http://localhost:8000/api/hotel/sync/"
```

**Get specific hotel details:**
```bash
curl "http://localhost:8000/api/hotel/ai/details/2/"
```

**Incremental sync (hotels changed in last 24 hours):**
```bash
curl "http://localhost:8000/api/hotel/sync/?since=$(date -u -d '24 hours ago' '+%Y-%m-%dT%H:%M:%SZ')"
```

---

## Performance Considerations

### Bulk Sync Endpoint
- **Response Time**: ~100-200ms for 20 hotels
- **Data Size**: ~50-100KB per response
- **Recommendation**: Cache responses for 6 hours, use `since` for updates

### Real-Time Detail Endpoint
- **Response Time**: ~50ms per request (very fast)
- **Ideal for**: On-the-fly verification during chat
- **Recommendation**: Can call freely without rate limiting (no auth required)

---

## Integration Steps for Your AI

1. **Initial Setup** (run once):
   ```python
   response = requests.get("http://localhost:8000/api/hotel/sync/")
   hotels = response.json()['hotels']
   # Create embeddings for each hotel's description
   embeddings = create_embeddings([h['description'] for h in hotels])
   save_to_vector_db(embeddings, hotels)
   ```

2. **Scheduled Sync** (every 6 hours):
   ```python
   last_sync = get_last_sync_time()
   response = requests.get(f"http://localhost:8000/api/hotel/sync/?since={last_sync}")
   # Update only changed hotels in vector DB
   ```

3. **During Chat** (when recommending):
   ```python
   # Search embeddings to get matching hotels
   matching_hotel_ids = search_similar_hotels(user_query)
   
   # Verify each with real-time endpoint
   for hotel_id in matching_hotel_ids:
       details = requests.get(f"/api/hotel/ai/details/{hotel_id}/")
       if details['hotel']['base_price_per_night'] < user_budget:
           recommend(details['hotel'])
   ```

---

## Future Enhancements

- [ ] Add API key authentication for production
- [ ] Implement rate limiting
- [ ] Add caching headers for better performance
- [ ] Support for availability/booking status
- [ ] Guest reviews and feedback integration
- [ ] Price history/trends endpoint

