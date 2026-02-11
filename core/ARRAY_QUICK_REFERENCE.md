# Quick Reference - Hotel Array Data API

## TL;DR - Just Tell Me How to Use It!

Send images and amenities as **arrays of strings**:

```bash
curl -X PATCH http://localhost:8000/api/hotel/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "images": ["url1", "url2", "url3"],
    "amenities": ["WiFi", "Pool", "Gym"]
  }'
```

## Limits

- **Images**: Max 10
- **Amenities**: Max 20
- **Each item**: Non-empty string
- **Empty arrays**: OK

## Valid Examples ✓

```json
{
  "images": [],
  "amenities": []
}
```

```json
{
  "images": ["https://example.com/1.jpg"],
  "amenities": ["Free WiFi"]
}
```

```json
{
  "images": [
    "https://example.com/img1.jpg",
    "https://example.com/img2.jpg",
    "https://example.com/img3.jpg"
  ],
  "amenities": [
    "Free WiFi",
    "Swimming Pool",
    "Gym & Fitness",
    "Restaurant",
    "Room Service"
  ]
}
```

## Invalid Examples ✗

```json
// NOT an array
{
  "images": "single_image.jpg"
}
```

```json
// Empty strings not allowed
{
  "amenities": ["WiFi", "", "Pool"]
}
```

```json
// Too many
{
  "images": ["img1", "img2", ..., "img11"]  // Max 10
}
```

## Python Example

```python
import requests

headers = {"Authorization": f"Bearer {token}"}
data = {
    "images": ["url1", "url2"],
    "amenities": ["WiFi", "Pool"]
}

response = requests.patch(
    "http://localhost:8000/api/hotel/",
    headers=headers,
    json=data
)

# Get the arrays back
hotel = response.json()['hotel']
print(hotel['images'])      # ["url1", "url2"]
print(hotel['amenities'])   # ["WiFi", "Pool"]
```

## Database Format

Stored as **JSON arrays**:

```python
Hotel.objects.first().images    # ["url1", "url2"]
Hotel.objects.first().amenities # ["WiFi", "Pool"]
```

## API Response

```json
{
  "message": "Hotel updated successfully",
  "hotel": {
    "id": 1,
    "hotel_name": "Grand Hotel",
    "images": ["url1", "url2", "url3"],
    "amenities": ["WiFi", "Pool", "Gym"],
    "is_approved": "pending",
    ...
  }
}
```

## Validation Error Response

```json
{
  "images": ["Maximum 10 images allowed"]
}
```

or

```json
{
  "amenities": ["Each amenity must be a non-empty string"]
}
```

## Endpoints

| Method | URL | Data |
|--------|-----|------|
| GET | `/api/hotel/` | - |
| PATCH | `/api/hotel/` | `{"images": [...], "amenities": [...]}` |

## Authentication

```bash
# Step 1: Get token
curl -X POST http://localhost:8000/api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"user","password":"pass"}'

# Step 2: Use token in header
Authorization: Bearer YOUR_TOKEN
```

---

**For detailed documentation**, see [HOTEL_ARRAYS_API.md](HOTEL_ARRAYS_API.md)
