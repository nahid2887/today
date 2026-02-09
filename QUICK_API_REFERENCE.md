# Quick API Reference for AI Integration

## 🔗 Two Key Endpoints

### 1️⃣ Bulk Sync (For RAG/Embeddings)
```
GET http://localhost:8000/api/hotel/sync/
```
**Returns**: All 20 approved hotels with static data (names, descriptions, amenities)
**For**: Building initial embeddings and incremental updates
**Incremental**: Add `?since=2026-02-09T00:00:00Z` to get only changed hotels

### 2️⃣ Real-Time Details (For Verification)
```
GET http://localhost:8000/api/hotel/ai/details/{hotel_id}/
```
**Returns**: Current prices, active offers, commission rates
**For**: On-the-fly verification during chat recommendations
**Performance**: ~50ms per request

---

## 📊 Test Data Loaded

✅ **20 Approved Hotels**
- Hotels 2-21 in database
- Prices: $110 - $300/night
- All have `is_approved: "approved"`
- Each has 1-3 active special offers
- Ratings: 3.5 - 5.0 stars

✅ **20 Partner Accounts**
- Username: `partner_1` to `partner_20`
- Password: `testpass123`
- Each owns one approved hotel

---

## 🧪 Quick Tests

**Test Bulk Sync:**
```bash
curl "http://localhost:8000/api/hotel/sync/" | python -m json.tool
```

**Test Real-Time Detail (Hotel ID 2):**
```bash
curl "http://localhost:8000/api/hotel/ai/details/2/" | python -m json.tool
```

**Test with Filter (Get only new hotels):**
```bash
curl "http://localhost:8000/api/hotel/sync/?since=2026-02-09T08:00:00Z"
```

---

## 📋 Response Examples

### Bulk Sync Response
```json
{
  "message": "Synced 20 approved hotels",
  "count": 20,
  "hotels": [
    {
      "id": 2,
      "hotel_name": "Grand Plaza Hotel",
      "description": "Luxury 5-star hotel...",
      "location": "123 Main St, Downtown",
      "city": "New York",
      "country": "USA",
      "amenities": ["Free WiFi", "Pool", "Gym", ...],
      "average_rating": "3.53",
      "total_ratings": 437,
      "last_updated": "2026-02-09T08:25:46.098126+00:00"
    }
  ]
}
```

### Real-Time Detail Response
```json
{
  "message": "Hotel details retrieved successfully",
  "hotel": {
    "id": 2,
    "hotel_name": "Grand Plaza Hotel",
    "base_price_per_night": "250.00",
    "commission_rate": "2.96",
    "active_special_offers": [
      {
        "discount_percentage": 25.0,
        "special_perks": ["Free fitness center", "Free coffee"],
        "valid_until": "2026-03-13"
      }
    ],
    "is_approved": "approved",
    "updated_at": "2026-02-09T08:25:46.098126Z"
  }
}
```

---

## 🚀 Integration Workflow

1. **Initial Setup**:
   - Fetch `/api/hotel/sync/` (all hotels)
   - Create embeddings from descriptions
   - Store in vector DB

2. **Scheduled Updates** (every 6 hours):
   - Fetch `/api/hotel/sync/?since=<last_sync_time>`
   - Update vector DB with new/changed hotels

3. **During Chat**:
   - User: "Find me a hotel in New York under $200/night"
   - Search vector DB for similar hotels
   - For each match, call `/api/hotel/ai/details/{id}/`
   - Filter by price and recommend

---

## 📝 Database Info

**PostgreSQL Connection:**
- Host: `db` (or `localhost` from host machine)
- Port: `5432`
- Database: `hotel_db`
- User: `hotel_user`
- Password: `hotel_pass`

**Schema:**
- Hotels table: 22 records (1 auto-created + 20 fake + 1 test)
- SpecialOffers table: ~40 records (multiple per hotel)
- Partners table: 20 records
- Users table: 20 records

---

## ✨ Key Features Implemented

✅ Auto-create hotel when partner account is created  
✅ Hotel requires admin approval (is_approved: pending/approved/rejected)  
✅ Partner can only update their own hotel  
✅ Updating hotel sets is_approved back to pending  
✅ 20 pre-loaded approved hotels for testing  
✅ Bulk sync endpoint for RAG/embeddings  
✅ Real-time detail endpoint for chat verification  
✅ No authentication required for AI endpoints (prod: add API key)

