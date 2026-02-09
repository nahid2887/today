# Hotel API - Images and Amenities Array Handling

## Overview

The Hotel API now properly supports **arrays/lists** for both `images` and `amenities` fields. These fields can store multiple values and include validation to ensure data integrity.

## Field Specifications

### Images Field
- **Type**: Array of strings
- **Maximum items**: 10 images
- **Format**: URLs or file paths (non-empty strings)
- **Required**: No (optional)
- **Empty arrays**: Allowed

### Amenities Field
- **Type**: Array of strings
- **Maximum items**: 20 amenities
- **Format**: Amenity names (non-empty strings)
- **Required**: No (optional)
- **Empty arrays**: Allowed

## API Endpoints

### Update Hotel (PATCH)
**URL**: `POST /api/hotel/`  
**Authentication**: Required (Bearer token)  
**Permission**: Partner user only

#### Request Body Example:
```json
{
  "hotel_name": "Luxury Grand Hotel",
  "location": "123 Main Street, Downtown",
  "city": "New York",
  "country": "USA",
  "number_of_rooms": 150,
  "room_type": "deluxe",
  "base_price_per_night": 250.00,
  "description": "A world-class luxury hotel with premium amenities",
  "commission_rate": 5.5,
  "images": [
    "https://example.com/images/exterior.jpg",
    "https://example.com/images/lobby.jpg",
    "https://example.com/images/room.jpg",
    "https://example.com/images/pool.jpg"
  ],
  "amenities": [
    "Free WiFi",
    "Swimming Pool",
    "Gym & Fitness Center",
    "Restaurant",
    "Room Service",
    "Spa & Massage"
  ]
}
```

#### Response Example (200 OK):
```json
{
  "message": "Hotel updated successfully. Status set to pending for admin review.",
  "hotel": {
    "id": 1,
    "hotel_name": "Luxury Grand Hotel",
    "location": "123 Main Street, Downtown",
    "city": "New York",
    "country": "USA",
    "number_of_rooms": 150,
    "room_type": "deluxe",
    "description": "A world-class luxury hotel with premium amenities",
    "base_price_per_night": "250.00",
    "images": [
      "https://example.com/images/exterior.jpg",
      "https://example.com/images/lobby.jpg",
      "https://example.com/images/room.jpg",
      "https://example.com/images/pool.jpg"
    ],
    "amenities": [
      "Free WiFi",
      "Swimming Pool",
      "Gym & Fitness Center",
      "Restaurant",
      "Room Service",
      "Spa & Massage"
    ],
    "is_approved": "pending",
    "rejection_reason": null,
    "average_rating": "0.00",
    "total_ratings": 0,
    "commission_rate": "5.50",
    "created_at": "2026-02-09T10:30:00Z",
    "updated_at": "2026-02-09T10:35:00Z"
  }
}
```

### Get Hotel (GET)
**URL**: `GET /api/hotel/`  
**Authentication**: Required (Bearer token)

#### Response Example (200 OK):
```json
{
  "message": "Hotel retrieved successfully",
  "hotel": {
    "id": 1,
    "hotel_name": "Luxury Grand Hotel",
    "images": [
      "https://example.com/images/exterior.jpg",
      "https://example.com/images/lobby.jpg"
    ],
    "amenities": [
      "Free WiFi",
      "Swimming Pool",
      "Gym"
    ],
    "is_approved": "pending"
  }
}
```

## Validation Rules

### Images Validation
| Rule | Details |
|------|---------|
| **Type** | Must be an array of strings |
| **Max Length** | 10 images maximum |
| **Empty Strings** | Not allowed within array |
| **Min Length** | No minimum (can be empty array `[]`) |

**Error Examples**:
```json
// ❌ Too many images
{
  "images": ["image1.jpg", "image2.jpg", ..., "image11.jpg"]
}
// Response: "Maximum 10 images allowed"

// ❌ Not an array
{
  "images": "single_image.jpg"
}
// Response: "Images must be an array/list"

// ❌ Empty string in array
{
  "images": ["", "image2.jpg"]
}
// Response: "Each image must be a non-empty string"
```

### Amenities Validation
| Rule | Details |
|------|---------|
| **Type** | Must be an array of strings |
| **Max Length** | 20 amenities maximum |
| **Empty Strings** | Not allowed within array |
| **Min Length** | No minimum (can be empty array `[]`) |

**Error Examples**:
```json
// ❌ Too many amenities
{
  "amenities": ["WiFi", "Pool", ..., "21st amenity"]
}
// Response: "Maximum 20 amenities allowed"

// ❌ Empty string in array
{
  "amenities": ["Free WiFi", "", "Gym"]
}
// Response: "Each amenity must be a non-empty string"
```

## CURL Examples

### 1. Authenticate and get token
```bash
curl -X POST http://localhost:8000/api/token/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "partner1",
    "password": "password123"
  }'

# Response includes: access_token, refresh_token
```

### 2. Update hotel with images and amenities
```bash
curl -X PATCH http://localhost:8000/api/hotel/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "hotel_name": "Grand Hotel",
    "city": "New York",
    "images": [
      "https://example.com/image1.jpg",
      "https://example.com/image2.jpg",
      "https://example.com/image3.jpg"
    ],
    "amenities": [
      "Free WiFi",
      "Swimming Pool",
      "Gym",
      "Restaurant",
      "Room Service"
    ]
  }'
```

### 3. Get hotel with arrays
```bash
curl -X GET http://localhost:8000/api/hotel/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json"
```

### 4. Update with empty arrays
```bash
curl -X PATCH http://localhost:8000/api/hotel/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "images": [],
    "amenities": []
  }'
```

## Python Examples

### Using requests library
```python
import requests

# Get token
response = requests.post('http://localhost:8000/api/token/', json={
    'username': 'partner1',
    'password': 'password123'
})
token = response.json()['access']

# Update hotel with arrays
headers = {'Authorization': f'Bearer {token}'}
data = {
    'hotel_name': 'Grand Hotel',
    'images': [
        'https://example.com/image1.jpg',
        'https://example.com/image2.jpg'
    ],
    'amenities': [
        'Free WiFi',
        'Swimming Pool',
        'Gym'
    ]
}

response = requests.patch(
    'http://localhost:8000/api/hotel/',
    headers=headers,
    json=data
)

# Retrieve hotel
response = requests.get(
    'http://localhost:8000/api/hotel/',
    headers=headers
)

hotel = response.json()['hotel']
print(f"Images: {hotel['images']}")
print(f"Amenities: {hotel['amenities']}")
```

## Database Storage

Both `images` and `amenities` are stored as **JSON arrays** in the database:

```sql
-- Example database storage
{
  "images": [
    "https://example.com/image1.jpg",
    "https://example.com/image2.jpg"
  ],
  "amenities": [
    "Free WiFi",
    "Swimming Pool",
    "Gym"
  ]
}
```

## Common Scenarios

### Adding images one by one
```json
// Get current hotel
GET /api/hotel/

// Get response with existing images
"images": ["image1.jpg", "image2.jpg"]

// Add new image to array
PATCH /api/hotel/
{
  "images": ["image1.jpg", "image2.jpg", "image3.jpg"]
}
```

### Removing amenities
```json
// Get current hotel with amenities
GET /api/hotel/

// Return only desired amenities
PATCH /api/hotel/
{
  "amenities": ["Free WiFi", "Gym", "Restaurant"]
}
```

### Clear all images
```json
PATCH /api/hotel/
{
  "images": []
}
```

## Data Types Supported

| Type | Accepted | Example |
|------|----------|---------|
| URLs | ✓ | `"https://example.com/image.jpg"` |
| File paths | ✓ | `"/media/hotels/image.jpg"` |
| Relative paths | ✓ | `"images/hotel.jpg"` |
| Empty array | ✓ | `[]` |
| Non-empty strings | ✓ | `"Free WiFi"`, `"Room Service"` |
| Numbers | ✗ | `[1, 2, 3]` |
| Objects | ✗ | `[{"url": "..."}, ...]` |
| null | ✗ | `[null, "image.jpg"]` |
| Empty strings | ✗ | `["", "image.jpg"]` |

## Notes

- **Case Sensitive**: The API field names (`images`, `amenities`) are case-sensitive
- **Partial Updates**: You can update only `images` or only `amenities` without sending all fields
- **Auto-pending**: Any update to hotel information resets `is_approved` to `'pending'` for admin review
- **No Duplicates Validation**: Duplicate entries are currently allowed (can be added in future)
- **Order Preserved**: The array order is maintained as sent
