# 🖼️ Hotel Image Upload Guide

## ✅ New Feature: Upload Images via PATCH/POST

You can now **upload actual image files** to your hotel! No need to send URLs anymore.

---

## 🚀 How to Upload Images

### Option 1: Upload Single Image (Recommended)

**Endpoint**: `POST /api/hotel/upload-image/`

**In Postman**:

1. **Method**: POST
2. **URL**: `http://localhost:8000/api/hotel/upload-image/`
3. **Authorization**: Bearer token (Tab: Authorization)
4. **Body**: form-data
   - Key: `image`
   - Type: File
   - Value: Select your image file

**Response**:
```json
{
  "message": "Image uploaded successfully",
  "image_url": "/media/hotel_images/1/abc123.jpg",
  "hotel_id": 1,
  "hotel_images": [
    "/media/hotel_images/1/abc123.jpg"
  ]
}
```

The image URL is **automatically added to your hotel's images array**! ✅

---

### Option 2: Send Multiple Images with Form-Data (PATCH)

**Endpoint**: `PATCH /api/hotel/`

You can now use form-data to send files directly:

**In Postman**:
1. **Method**: PATCH
2. **URL**: `http://localhost:8000/api/hotel/`
3. **Body**: form-data
   - You can mix text fields and files in same request

**However**, currently the best workflow is:
1. **Upload each image** using the upload endpoint (gets URL)
2. **Update hotel** with the returned URLs

---

## 📋 Step-by-Step Tutorial

### Step 1: Get Authentication Token
```bash
curl -X POST http://localhost:8000/api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"partner1","password":"password"}'

# Copy the access token
```

### Step 2: Upload Image #1
```bash
curl -X POST http://localhost:8000/api/hotel/upload-image/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "image=@/path/to/image1.jpg"

# Response:
# {
#   "image_url": "/media/hotel_images/1/uuid1.jpg",
#   "hotel_images": ["/media/hotel_images/1/uuid1.jpg"]
# }
```

### Step 3: Upload Image #2
```bash
curl -X POST http://localhost:8000/api/hotel/upload-image/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "image=@/path/to/image2.jpg"

# Response:
# {
#   "image_url": "/media/hotel_images/1/uuid2.jpg",
#   "hotel_images": [
#     "/media/hotel_images/1/uuid1.jpg",
#     "/media/hotel_images/1/uuid2.jpg"
#   ]
# }
```

### Step 4: Update Hotel with Other Fields
```bash
curl -X PATCH http://localhost:8000/api/hotel/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "hotel_name": "My Grand Hotel",
    "amenities": ["WiFi", "Pool", "Gym"]
  }'

# Images are already stored from uploads!
```

### Step 5: Retrieve Your Hotel
```bash
curl -X GET http://localhost:8000/api/hotel/ \
  -H "Authorization: Bearer YOUR_TOKEN"

# Response includes:
# {
#   "images": [
#     "/media/hotel_images/1/uuid1.jpg",
#     "/media/hotel_images/1/uuid2.jpg"
#   ],
#   "amenities": ["WiFi", "Pool", "Gym"]
# }
```

---

## 🖼️ In Postman (Visual Guide)

### Upload Single Image

```
POST http://localhost:8000/api/hotel/upload-image/

Headers:
  Authorization: Bearer YOUR_TOKEN

Body → form-data:
  Key: image
  Type: File
  Value: [Select image file from computer]

Click: Send
```

**Response**:
```json
{
  "message": "Image uploaded successfully",
  "image_url": "/media/hotel_images/1/a1b2c3d4.jpg",
  "hotel_id": 1,
  "hotel_images": ["/media/hotel_images/1/a1b2c3d4.jpg"]
}
```

---

## 📝 Supported Image Formats

✅ JPEG (.jpg, .jpeg)  
✅ PNG (.png)  
✅ GIF (.gif)  
✅ WebP (.webp)  

❌ BMP, TIFF, SVG

---

## 📦 Constraints

| Constraint | Value |
|-----------|-------|
| **Max file size** | 5 MB |
| **Max images per hotel** | 10 |
| **Allowed formats** | JPEG, PNG, GIF, WebP |
| **Storage location** | `media/hotel_images/{hotel_id}/` |

---

## 🔄 Complete Workflow

```
1. Login → Get Token
   POST /api/token/
   
2. Upload Image → Get URL
   POST /api/hotel/upload-image/
   Response: image_url (auto-added to hotel.images)
   
3. Repeat Step 2 for each image
   
4. Update hotel info (optional)
   PATCH /api/hotel/
   (images already saved from uploads)
   
5. Get your hotel
   GET /api/hotel/
   Response includes images array with all uploaded images
```

---

## 🔗 Generated URLs

When you upload an image, it's stored at:
```
Server: /media/hotel_images/{hotel_id}/{uuid}.{ext}
URL: /media/hotel_images/1/a1b2c3d4-e5f6-47a8-9b0c-1d2e3f4a5b6c.jpg
Access: http://localhost:8000/media/hotel_images/1/a1b2c3d4-e5f6-47a8-9b0c-1d2e3f4a5b6c.jpg
```

---

## ✨ Features

✅ **Automatic URL Generation** - No need to manually set URLs  
✅ **Unique Filenames** - Uses UUID to prevent conflicts  
✅ **File Validation** - Checks size and type  
✅ **Direct Array Addition** - URL auto-added to hotel.images  
✅ **Easy Integration** - Works with Postman form-data  
✅ **Organized Storage** - Files sorted by hotel ID  

---

## 🐍 Python Example

```python
import requests

# Get token
response = requests.post('http://localhost:8000/api/token/', json={
    'username': 'partner1',
    'password': 'password'
})
token = response.json()['access']

headers = {'Authorization': f'Bearer {token}'}

# Upload image
with open('hotel_image.jpg', 'rb') as f:
    files = {'image': f}
    response = requests.post(
        'http://localhost:8000/api/hotel/upload-image/',
        headers=headers,
        files=files
    )

print(response.json())
# Output:
# {
#   "message": "Image uploaded successfully",
#   "image_url": "/media/hotel_images/1/uuid.jpg",
#   "hotel_images": ["/media/hotel_images/1/uuid.jpg"]
# }

# Image is now in your hotel's images array!
```

---

## 🎯 API Endpoints Reference

### Upload Image
```
POST /api/hotel/upload-image/
Content-Type: multipart/form-data
Authorization: Bearer TOKEN

Form Data:
  image: [binary file]

Returns:
  200 OK:
    - message
    - image_url
    - hotel_id
    - hotel_images (updated array)
    
  400 Bad Request:
    - No image file provided
    - File too large
    - Invalid format
    
  403 Forbidden:
    - Not a partner account
```

### Update Hotel with Images Array
```
PATCH /api/hotel/
Content-Type: application/json
Authorization: Bearer TOKEN

Body:
  {
    "images": ["url1", "url2"],
    "amenities": ["WiFi", "Pool"]
  }

Returns:
  200 OK: Updated hotel object
```

### Get Hotel with Images
```
GET /api/hotel/
Authorization: Bearer TOKEN

Returns:
  {
    "images": ["/media/hotel_images/1/uuid1.jpg", ...],
    "amenities": ["WiFi", "Pool"],
    ...
  }
```

---

## 🔧 File Structure

```
media/
└── hotel_images/
    ├── 1/
    │   ├── a1b2c3d4-e5f6-47a8-9b0c-1d2e3f4a5b6c.jpg
    │   ├── b2c3d4e5-f6a7-48b9-0c1d-2e3f4a5b6c7d.jpg
    │   └── c3d4e5f6-a7b8-49ca-1d2e-3f4a5b6c7d8e.jpg
    └── 2/
        ├── d4e5f6a7-b8c9-50db-2e3f-4a5b6c7d8e9f.jpg
        └── e5f6a7b8-c9da-51ec-3f4a-5b6c7d8e9f0a.jpg
```

---

## 🆘 Troubleshooting

### "No image file provided"
**Solution**: Make sure you:
- Selected **form-data** in Postman body
- Set Key name to exactly `image` (case-sensitive)
- Set Type to **File** (not Text)
- Selected an actual file

### "File size exceeds maximum limit"
**Solution**: Your image is larger than 5MB
- Compress the image
- Use a smaller format (JPEG instead of PNG)
- Resize the image before uploading

### "Invalid image format"
**Solution**: Your file format is not supported
- Use: JPEG, PNG, GIF, or WebP
- Convert your image to one of these formats

### "Hotel not found"
**Solution**: You're not a partner or hotel wasn't created
- Make sure you're logged in as a partner account
- Partner accounts auto-create hotels

---

## 🚀 Next Steps

1. ✅ Upload your first image
2. ✅ Verify it appears in `GET /api/hotel/`
3. ✅ Upload multiple images
4. ✅ Update hotel info (amenities, etc.)
5. ✅ Build your frontend with this API

---

## 📞 Summary

**Old way**: Send image URLs manually  
**New way**: Upload files → Auto-added to images array ✅

**Endpoints**:
- `POST /api/hotel/upload-image/` - Upload image file
- `PATCH /api/hotel/` - Update hotel data
- `GET /api/hotel/` - Get hotel with images

**Status**: ✅ Ready to use
