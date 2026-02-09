# Implementation Details - How Arrays Work

## Model Definition

In [hotel/models.py](hotel/models.py), images and amenities are defined as JSON fields:

```python
# Property Images (multiple images support)
images = models.JSONField(
    default=list,
    blank=True,
    help_text="List of image URLs/paths for the hotel property"
)

# Amenities (as JSON or separate fields)
amenities = models.JSONField(
    default=list, 
    blank=True,
    help_text="List of amenities like ['Free WiFi', 'Pool', 'Gym', 'Restaurant']"
)
```

These JSONFields automatically handle serialization/deserialization of Python lists to/from JSON.

## Serializer Implementation

In [hotel/serializers.py](hotel/serializers.py), we use `ListField` to properly validate arrays:

```python
class HotelSerializer(serializers.ModelSerializer):
    # Override default JSON behavior with explicit ListField
    images = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
        help_text="Array of image URLs/paths"
    )
    
    amenities = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
        help_text="Array of amenities"
    )
    
    # Validation methods
    def validate_images(self, value):
        """Validate images array"""
        if not isinstance(value, list):
            raise serializers.ValidationError("Images must be an array/list")
        if len(value) > 10:
            raise serializers.ValidationError("Maximum 10 images allowed")
        for img in value:
            if not isinstance(img, str) or len(img.strip()) == 0:
                raise serializers.ValidationError("Each image must be a non-empty string")
        return value
    
    def validate_amenities(self, value):
        """Validate amenities array"""
        if not isinstance(value, list):
            raise serializers.ValidationError("Amenities must be an array/list")
        if len(value) > 20:
            raise serializers.ValidationError("Maximum 20 amenities allowed")
        for amenity in value:
            if not isinstance(amenity, str) or len(amenity.strip()) == 0:
                raise serializers.ValidationError("Each amenity must be a non-empty string")
        return value
```

## Data Flow

### Request Flow (Client → Server)

1. **Client sends JSON array**:
   ```json
   {
     "images": ["img1.jpg", "img2.jpg"],
     "amenities": ["WiFi", "Pool"]
   }
   ```

2. **Django REST Framework receives it**:
   - JSON is parsed automatically
   - Serializer `ListField` processes it
   - Validation methods are called

3. **Validation happens**:
   - Check if it's a list: `isinstance(value, list)`
   - Check length limits: `len(value) > 10`
   - Check individual items: `len(img.strip()) == 0`

4. **Data is saved to database**:
   ```python
   hotel.images = ["img1.jpg", "img2.jpg"]
   hotel.amenities = ["WiFi", "Pool"]
   hotel.save()
   ```

5. **Stored as JSON in database**:
   ```sql
   -- SQLite/PostgreSQL
   UPDATE hotel SET 
    images = '["img1.jpg", "img2.jpg"]',
    amenities = '["WiFi", "Pool"]'
   ```

### Response Flow (Server → Client)

1. **Django retrieves data from database**:
   ```python
   hotel = Hotel.objects.get(id=1)
   print(hotel.images)    # ['img1.jpg', 'img2.jpg']
   print(hotel.amenities) # ['WiFi', 'Pool']
   ```

2. **Serializer converts to response**:
   ```python
   serializer = HotelSerializer(hotel)
   return Response(serializer.data)
   ```

3. **JSON response sent to client**:
   ```json
   {
     "id": 1,
     "images": ["img1.jpg", "img2.jpg"],
     "amenities": ["WiFi", "Pool"]
   }
   ```

## Validation Chain

```
Client JSON Array
       ↓
Django REST Framework Parser
       ↓
Serializer ListField Processing
       ↓
Custom validate_images() / validate_amenities()
       ↓
Type Check (is list?)
       ↓
Length Check (max 10/20?)
       ↓
Content Check (non-empty strings?)
       ↓
Valid ✓ → Save to Database
Invalid ✗ → Return Error
```

## Examples by Scenario

### Scenario 1: Add hotel with images and amenities

```python
# Request
{
  "hotel_name": "Grand Hotel",
  "images": ["exterior.jpg", "lobby.jpg"],
  "amenities": ["WiFi", "Pool"]
}

# Serializer Processing
# 1. HotelSerializer receives data
# 2. validate_images() checks:
#    - Is ['exterior.jpg', 'lobby.jpg'] a list? YES ✓
#    - Length <= 10? YES (2 <= 10) ✓
#    - All non-empty strings? YES ✓
# 3. validate_amenities() checks:
#    - Is ['WiFi', 'Pool'] a list? YES ✓
#    - Length <= 20? YES (2 <= 20) ✓
#    - All non-empty strings? YES ✓
# 4. All valid → Create hotel

# Database (SQLite)
INSERT INTO hotel (hotel_name, images, amenities) 
VALUES ('Grand Hotel', '["exterior.jpg", "lobby.jpg"]', '["WiFi", "Pool"]');

# Response
{
  "id": 1,
  "hotel_name": "Grand Hotel",
  "images": ["exterior.jpg", "lobby.jpg"],
  "amenities": ["WiFi", "Pool"]
}
```

### Scenario 2: Update with more images

```python
# Current hotel
hotel.images = ["img1.jpg", "img2.jpg"]
hotel.amenities = ["WiFi"]

# Request: Add image
{
  "images": ["img1.jpg", "img2.jpg", "img3.jpg", "img4.jpg"],
  "amenities": ["WiFi", "Pool", "Gym"]
}

# Validation passes
# Database updated
# Response returns new arrays
```

### Scenario 3: Clear all images

```python
# Request
{
  "images": [],
  "amenities": ["WiFi"]
}

# Validation
# - Is [] a list? YES ✓
# - allow_empty=True? YES ✓
# Valid → Update

# Database
hotel.images = []
hotel.amenities = ["WiFi"]
```

### Scenario 4: Invalid - empty string

```python
# Request
{
  "images": ["img1.jpg", "", "img3.jpg"]
}

# Validation
# - Is it a list? YES ✓
# - Length <= 10? YES ✓
# - All non-empty strings? NO ✗
#   → Empty string found at index 1

# Error Response
{
  "images": ["Each image must be a non-empty string"]
}

# HTTP 400 Bad Request
```

## Why ListField Instead of JSONField?

| Aspect | JSONField | ListField |
|--------|-----------|-----------|
| **Parsing** | Automatic JSON parsing | DRF validation |
| **Validation** | No built-in validation | Full validation support |
| **Error Messages** | Generic | Specific error messages |
| **Type Checking** | No | Yes (must be list) |
| **Item Validation** | No | Yes (via child parameter) |
| **API Documentation** | Poor | Excellent (Swagger/OpenAPI) |

## Database Compatibility

The implementation works with:

- **SQLite** (default): Stores as TEXT JSON
- **PostgreSQL** (recommended): Uses native JSON type
- **MySQL**: Supports JSON type
- **MariaDB**: Supports JSON type

All databases automatically handle JSON serialization/deserialization.

## Performance Considerations

1. **Index Support**: JSONField doesn't create indexes on array items
   - To index, use separate many-to-one relationship:
   ```python
   class HotelImage(models.Model):
       hotel = models.ForeignKey(Hotel, related_name='image_list')
       url = models.URLField()
   ```

2. **Query Performance**: 
   - Small arrays (< 20 items): JSONField is fine
   - Large arrays (> 100 items): Consider separate table

3. **Filtering**:
   ```python
   # Can't directly filter by array contents with JSONField
   # Would need separate table or raw SQL
   ```

## Security

The implementation is secure because:

1. ✅ **Type Validation**: Only strings accepted
2. ✅ **Length Limits**: Max 10 images, 20 amenities
3. ✅ **Content Validation**: Non-empty strings only
4. ✅ **No Code Execution**: JSON is data, not code
5. ✅ **SQL Injection Protected**: ORM handles escaping

## Future Enhancements

1. **Add unique constraint**:
   ```python
   def validate_images(self, value):
       if len(value) != len(set(value)):
           raise ValidationError("Duplicate images not allowed")
   ```

2. **Add URL validation**:
   ```python
   def validate_images(self, value):
       for img in value:
           try:
               urlparse(img)
           except:
               raise ValidationError("Invalid URL format")
   ```

3. **Add async image validation**:
   ```python
   async def validate_images_exist(self, value):
       for img in value:
           response = await aiohttp.head(img)
           if response.status != 200:
               raise ValidationError(f"Image {img} not accessible")
   ```

4. **Support nested objects**:
   ```python
   images = serializers.ListField(
       child=serializers.DictField(child=serializers.CharField()),
       # [{"url": "...", "caption": "..."}, ...]
   )
   ```
