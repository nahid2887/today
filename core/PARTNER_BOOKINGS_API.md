# Hotel Partner Bookings Management API

## Overview
The Partner Bookings API provides hotel managers with a unified, single-view endpoint to manage all bookings for their hotel. This API brings together booking list and details in one comprehensive interface.

---

## Endpoint

### GET `/api/hotel/manager/bookings/`

**Authentication Required:** Yes (Must be a partner user)  
**Content-Type:** `application/json`  
**Rate Limiting:** Standard API rate limits apply

---

## Features

✅ **Single Unified View** - View all bookings and booking details in one place  
✅ **Real-Time Statistics** - Get booking statistics at a glance  
✅ **Powerful Filtering** - Filter by status, date range, or guest name  
✅ **Detailed Information** - View complete booking details including guest info and pricing  
✅ **Revenue Tracking** - Track total revenue from your bookings

---

## Query Parameters

### `status` (Optional)
Filter bookings by status. Allowed values:
- `pending` - Pending confirmation
- `confirmed` - Confirmed bookings
- `cancelled` - Cancelled bookings
- `completed` - Completed bookings

**Example:**
```
GET /api/hotel/manager/bookings/?status=confirmed
```

### `booking_id` (Optional)
Get detailed information about a specific booking. When provided, returns detailed view of a single booking instead of list view.

**Example:**
```
GET /api/hotel/manager/bookings/?booking_id=123
```

### `date_from` (Optional)
Filter bookings from this date onwards. Format: `YYYY-MM-DD`

**Example:**
```
GET /api/hotel/manager/bookings/?date_from=2025-02-01
```

### `date_to` (Optional)
Filter bookings until this date. Format: `YYYY-MM-DD`

**Example:**
```
GET /api/hotel/manager/bookings/?date_to=2025-02-28
```

### `guest_name` (Optional)
Search by guest/traveler name (searches first name, last name, and username).

**Example:**
```
GET /api/hotel/manager/bookings/?guest_name=John
```

---

## Response Format

### List View Response (Default)

```json
{
  "message": "Retrieved 5 booking(s) for hotel: The Grand Azure",
  "hotel_id": 22,
  "hotel_name": "The Grand Azure",
  "statistics": {
    "total_bookings": 5,
    "pending": 1,
    "confirmed": 3,
    "cancelled": 0,
    "completed": 1,
    "total_revenue": "$2520.00"
  },
  "filters_applied": {
    "status": "confirmed",
    "date_from": null,
    "date_to": null,
    "guest_name": null
  },
  "results": [
    {
      "id": 1,
      "hotel": 22,
      "hotel_name": "The Grand Azure",
      "hotel_city": "New York",
      "traveler_name": "John",
      "traveler_email": "john@example.com",
      "check_in_date": "2025-01-15",
      "check_out_date": "2025-01-18",
      "number_of_guests": 2,
      "number_of_nights": 3,
      "price_per_night": "$100.00",
      "total_price": "$300.00",
      "final_price": "$300.00",
      "status": "confirmed",
      "created_at": "2025-01-10T10:00:00Z"
    },
    {
      "id": 2,
      "hotel": 22,
      "hotel_name": "The Grand Azure",
      "hotel_city": "New York",
      "traveler_name": "Jane",
      "traveler_email": "jane@example.com",
      "check_in_date": "2025-01-20",
      "check_out_date": "2025-01-25",
      "number_of_guests": 4,
      "number_of_nights": 5,
      "price_per_night": "$150.00",
      "total_price": "$750.00",
      "final_price": "$750.00",
      "status": "confirmed",
      "created_at": "2025-01-12T14:30:00Z"
    }
  ]
}
```

### Detail View Response (When `booking_id` is provided)

```json
{
  "message": "Booking details retrieved successfully",
  "hotel_id": 22,
  "hotel_name": "The Grand Azure",
  "booking": {
    "id": 1,
    "traveler_name": "John",
    "traveler_email": "john@example.com",
    "hotel_details": {
      "id": 22,
      "partner_name": "grand_azure",
      "hotel_name": "The Grand Azure",
      "city": "New York",
      "country": "USA",
      "room_type": "deluxe",
      "base_price_per_night": "$100.00",
      "images": [],
      "average_rating": 4.5,
      "total_ratings": 120,
      "is_approved": "approved"
    },
    "check_in_date": "2025-01-15",
    "check_out_date": "2025-01-18",
    "number_of_guests": 2,
    "number_of_nights": 3,
    "price_per_night": "$100.00",
    "total_price": "$300.00",
    "discount_percentage": 0,
    "discount_amount": 0,
    "final_price": "$300.00",
    "special_perks": [],
    "special_requests": "High floor room preferred",
    "status": "confirmed",
    "created_at": "2025-01-10T10:00:00Z",
    "updated_at": "2025-01-10T10:00:00Z"
  }
}
```

### Statistics Breakdown

The response includes helpful statistics:

- **total_bookings**: Total number of bookings (after filters applied)
- **pending**: Count of pending confirmations
- **confirmed**: Count of confirmed bookings
- **cancelled**: Count of cancelled bookings
- **completed**: Count of completed bookings
- **total_revenue**: Total revenue from confirmed and completed bookings

---

## Usage Examples

### Example 1: Get All Bookings
```bash
curl -X GET "http://api.example.com/api/hotel/manager/bookings/" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json"
```

###  Example 2: Get Confirmed Bookings Only
```bash
curl -X GET "http://api.example.com/api/hotel/manager/bookings/?status=confirmed" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json"
```

### Example 3: Get Bookings for Date Range
```bash
curl -X GET "http://api.example.com/api/hotel/manager/bookings/?date_from=2025-02-01&date_to=2025-02-28" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json"
```

### Example 4: Search by Guest Name
```bash
curl -X GET "http://api.example.com/api/hotel/manager/bookings/?guest_name=John" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json"
```

### Example 5: Get Specific Booking Details
```bash
curl -X GET "http://api.example.com/api/hotel/manager/bookings/?booking_id=123" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json"
```

### Example 6: Combined Filters
```bash
curl -X GET "http://api.example.com/api/hotel/manager/bookings/?status=confirmed&date_from=2025-02-01&guest_name=John" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json"
```

---

## Error Responses

### 403 - Not Authorized
```json
{
  "error": "Only hotel partners can access this endpoint",
  "detail": "You must be a registered hotel partner to view bookings"
}
```

**Status Code:** `403 Forbidden`

### 404 - Hotel Not Found
```json
{
  "error": "No hotel found for this partner",
  "detail": "Your hotel should have been auto-created with your partner account"
}
```

**Status Code:** `404 Not Found`

### 404 - Booking Not Found
```json
{
  "error": "Booking not found or does not belong to this hotel"
}
```

**Status Code:** `404 Not Found`

### 400 - Invalid Date Format
```json
{
  "error": "Invalid date format for date_from. Use YYYY-MM-DD"
}
```

**Status Code:** `400 Bad Request`

---

## Data Fields Explanation

### Booking Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | Integer | Unique booking ID |
| `traveler_name` | String | Guest's first name |
| `traveler_email` | String | Guest's email |
| `hotel_details` | Object | Complete hotel information |
| `check_in_date` | Date (YYYY-MM-DD) | Check-in date |
| `check_out_date` | Date (YYYY-MM-DD) | Check-out date |
| `number_of_guests` | Integer | Number of guests |
| `number_of_nights` | Integer | Calculated number of nights |
| `price_per_night` | Decimal | Nightly rate |
| `total_price` | Decimal | Total before discount |
| `discount_percentage` | Decimal | Applied discount % |
| `discount_amount` | Decimal | Applied discount amount |
| `final_price` | Decimal | Final price after discount |
| `special_perks` | Array | List of included perks |
| `special_requests` | String | Guest's special requests |
| `status` | String | Booking status (pending, confirmed, cancelled, completed) |
| `created_at` | DateTime | When booking was created |
| `updated_at` | DateTime | Last update timestamp |

---

## Filtering & Combining Filters

You can combine multiple filters for powerful queries:

```
GET /api/hotel/manager/bookings/?status=confirmed&date_from=2025-02-01&date_to=2025-02-28&guest_name=John
```

This would return:
- Only **confirmed** bookings
- Check-in DATE >= 2025-02-01
- Check-out DATE <= 2025-02-28
- Guest name contains "John"

---

## Best Practices

1. **Use Specific Filters** - Instead of fetching all bookings, use filters to get specific data
2. **Monitor Date Ranges** - Use `date_from` and `date_to` for better performance
3. **Check Statistics** - Review the statistics block to get quick insights
4. **Handle Errors Gracefully** - Always handle 403/404 errors for unauthorized access
5. **Share Booking Details** - Use `booking_id` parameter to get complete details for a specific booking

---

## Related Endpoints

- **Traveler Booking Management**: `GET/POST /api/hotel/bookings/`
- **Hotel Details**: `GET /api/hotel/<int:pk>/`
- **Special Offers**: `GET/POST /api/hotel/special-offers/`

---

## Version Info

- **API Version:** 1.0
- **Created:** February 2025
- **Last Updated:** February 2025

---

## Support

For issues or questions about this API, please contact the development team or refer to the main API documentation.
