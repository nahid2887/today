# Hotel Partner Bookings Management System

## 🎯 Overview

The Partner Bookings Management system provides hotel managers with a **single unified view** to see and manage all bookings for their hotel. 

### Key Highlights
✅ **Single API Endpoint** - All booking data in one place  
✅ **List + Detail View** - See all bookings or dive into individual booking details  
✅ **Real-Time Statistics** - Get revenue and booking status metrics instantly  
✅ **Advanced Filtering** - Filter by status, dates, or guest name  
✅ **Easy Integration** - Simple query parameters for powerful searches

---

## 🔌 API Endpoint

### Single Management Endpoint
```
GET /api/hotel/manager/bookings/
```

**Authentication:** Required (Partner user only)

---

## 📊 What Hotel Managers Can See

### 1. **Booking List View** (Default)
View all bookings for your hotel with key information:
- Guest name and email
- Check-in/Check-out dates
- Number of guests
- Price per night & total price
- Final price (after discounts)
- Booking status
- Creation date

### 2. **Detailed Booking View** (Using booking_id parameter)
Get complete information about a specific booking:
- All list view fields PLUS
- Hotel details information
- Special perks included
- Special requests from guest
- Pricing breakdown (base, discount, final)
- Update timestamps

### 3. **Revenue & Statistics Dashboard**
Every response includes:
- **Total bookings** count
- **Pending** confirmations
- **Confirmed** bookings
- **Cancelled** bookings
- **Completed** bookings
- **Total revenue** ($) from confirmed and completed bookings

---

## 🔍 Query Parameters

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `status` | string | Filter by booking status | `?status=confirmed` |
| `booking_id` | integer | Get details of specific booking | `?booking_id=123` |
| `date_from` | string (YYYY-MM-DD) | Filter from date onwards | `?date_from=2025-02-01` |
| `date_to` | string (YYYY-MM-DD) | Filter until date | `?date_to=2025-02-28` |
| `guest_name` | string | Search by traveler name | `?guest_name=John` |

### Status Values
- `pending` - Awaiting confirmation
- `confirmed` - Confirmed bookings
- `cancelled` - Cancelled bookings
- `completed` - Completed/checked-out bookings

---

## 📝 Usage Examples

### Example 1: View All Your Hotel's Bookings
```bash
curl -X GET "https://api.example.com/api/hotel/manager/bookings/" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Response includes:**
- All 50 bookings (example)
- Statistics: 50 total, 10 pending, 35 confirmed, 2 cancelled, 3 completed
- Total revenue: $5,240.00

---

### Example 2: See Only Confirmed Bookings
```bash
curl -X GET "https://api.example.com/api/hotel/manager/bookings/?status=confirmed" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Use Case:** Check your revenue from confirmed bookings

---

### Example 3: View Bookings for February 2025
```bash
curl -X GET "https://api.example.com/api/hotel/manager/bookings/?date_from=2025-02-01&date_to=2025-02-28" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Use Case:** Monthly revenue tracking

---

### Example 4: Find a Specific Guest's Booking
```bash
curl -X GET "https://api.example.com/api/hotel/manager/bookings/?guest_name=John" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Use Case:** Quick guest lookup

---

### Example 5: Get Complete Details of One Booking
```bash
curl -X GET "https://api.example.com/api/hotel/manager/bookings/?booking_id=42" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Response includes:**
- Complete booking details
- Guest full information
- Hotel details
- Special requests & perks
- Full pricing breakdown

---

### Example 6: Complex Filter - Confirmed Bookings in Feb by John
```bash
curl -X GET "https://api.example.com/api/hotel/manager/bookings/?status=confirmed&date_from=2025-02-01&date_to=2025-02-28&guest_name=John" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

---

## 📊 Sample Response - List View

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
    "status": null,
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
      "check_in_date": "2025-02-15",
      "check_out_date": "2025-02-18",
      "number_of_guests": 2,
      "number_of_nights": 3,
      "price_per_night": "$100.00",
      "total_price": "$300.00",
      "final_price": "$300.00",
      "status": "confirmed",
      "created_at": "2025-02-10T10:00:00Z"
    },
    {
      "id": 2,
      "hotel": 22,
      "hotel_name": "The Grand Azure",
      "hotel_city": "New York",
      "traveler_name": "Jane",
      "traveler_email": "jane@example.com",
      "check_in_date": "2025-02-20",
      "check_out_date": "2025-02-25",
      "number_of_guests": 4,
      "number_of_nights": 5,
      "price_per_night": "$150.00",
      "total_price": "$750.00",
      "final_price": "$750.00",
      "status": "confirmed",
      "created_at": "2025-02-12T14:30:00Z"
    }
  ]
}
```

---

## 📄 Sample Response - Detail View

```json
{
  "message": "Booking details retrieved successfully",
  "hotel_id": 22,
  "hotel_name": "The Grand Azure",
  "booking": {
    "id": 1,
    "traveler_name": "John",
    "traveler_email": "john.doe@example.com",
    "hotel_details": {
      "id": 22,
      "hotel_name": "The Grand Azure",
      "city": "New York",
      "country": "USA",
      "room_type": "deluxe",
      "base_price_per_night": "$100.00",
      "average_rating": 4.5,
      "total_ratings": 120,
      "is_approved": "approved"
    },
    "check_in_date": "2025-02-15",
    "check_out_date": "2025-02-18",
    "number_of_guests": 2,
    "number_of_nights": 3,
    "price_per_night": "$100.00",
    "total_price": "$300.00",
    "discount_percentage": 10,
    "discount_amount": "$30.00",
    "final_price": "$270.00",
    "special_perks": ["Free breakfast", "Late checkout"],
    "special_requests": "High floor room preferred, hypoallergenic pillow needed",
    "status": "confirmed",
    "created_at": "2025-02-10T10:00:00Z",
    "updated_at": "2025-02-10T12:30:00Z"
  }
}
```

---

## ✅ Integration Checklist for Hotel Managers

- [ ] Use the endpoint to build your booking dashboard
- [ ] Display statistics for quick insight
- [ ] Implement filtering for better UX
- [ ] Show guest details when clicked
- [ ] Track revenue monthly
- [ ] Share pending confirmations with team
- [ ] Export data for reporting (implement on frontend)

---

## 🚫 Error Handling

### Not Authenticated (No Partner Account)
```json
{
  "error": "Only hotel partners can access this endpoint",
  "detail": "You must be a registered hotel partner to view bookings"
}
```
**Status:** 403 Forbidden

### Hotel Not Found
```json
{
  "error": "No hotel found for this partner",
  "detail": "Your hotel should have been auto-created with your partner account"
}
```
**Status:** 404 Not Found

### Booking Not Found
```json
{
  "error": "Booking not found or does not belong to this hotel"
}
```
**Status:** 404 Not Found

### Invalid Date Format
```json
{
  "error": "Invalid date format for date_from. Use YYYY-MM-DD"
}
```
**Status:** 400 Bad Request

---

## 💡 Tips & Tricks

### Performance Tips
1. **Use date ranges** instead of fetching all bookings
2. **Filter by status** to see specific booking types
3. **Use booking_id** only when you need complete details
4. **Cache statistics** on the frontend to reduce API calls

### Business Insights
1. **Monitor pending bookings** - Convert to confirmed
2. **Track cancellations** - Identify patterns
3. **Calculate occupancy** - Use confirmed/completed bookings
4. **Monitor revenue** - Track monthly totals
5. **Analyze guest searches** - Use guest_name filter for popular guests

### Data Analysis
- Compare monthly revenue over time
- Identify peak booking periods
- Track booking source/channel patterns
- Monitor room type preferences

---

## 📌 Related APIs

| Endpoint | Purpose |
|----------|---------|
| `GET /api/hotel/` | Get your hotel profile |
| `POST /api/hotel/special-offers/` | Create special offers |
| `GET /api/hotel/special-offers/` | View your offers |
| `GET /api/hotel/bookings/` | Traveler booking management |

---

## 🎓 Common Scenarios

### Scenario 1: Daily Morning Check-In
```bash
# Get confirmed bookings for today
curl "https://api.example.com/api/hotel/manager/bookings/?status=confirmed&date_from=2025-02-13&date_to=2025-02-13"
```

### Scenario 2: Monthly Revenue Report
```bash
# Get confirmed and completed bookings for February
curl "https://api.example.com/api/hotel/manager/bookings/?status=confirmed&date_from=2025-02-01&date_to=2025-02-28"
curl "https://api.example.com/api/hotel/manager/bookings/?status=completed&date_from=2025-02-01&date_to=2025-02-28"
```

### Scenario 3: Handle Guest Request
```bash
# Find specific guest's booking
curl "https://api.example.com/api/hotel/manager/bookings/?guest_name=Smith"

# Get full details
curl "https://api.example.com/api/hotel/manager/bookings/?booking_id=456"
```

### Scenario 4: Identify No-Shows
```bash
# Get completed bookings
curl "https://api.example.com/api/hotel/manager/bookings/?status=completed"
```

---

## 📞 Support

For questions or issues:
1. Check this documentation
2. Review the example API requests
3. Contact the development team
4. Check API logs for errors

---

**Last Updated:** February 13, 2025  
**Version:** 1.0  
**API Status:** ✅ Active
