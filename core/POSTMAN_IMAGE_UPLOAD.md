# 📸 Image Upload - Postman Step-by-Step Guide

## ✅ Now You Can Upload Images!

The API now has a **new endpoint for uploading image files** directly!

---

## 🎯 Quick Start (Copy-Paste)

### Step 1: Get Your Token First

In Postman:

```
POST http://localhost:8000/api/token/

Body → raw → JSON:
{
  "username": "partner1",
  "password": "your_password"
}

Send → Copy the "access" value
```

**Result**: You get a token like `eyJ0eXAiOiJKV1QiLCJhbGc...`

---

### Step 2: Upload an Image

In Postman:

```
POST http://localhost:8000/api/hotel/upload-image/

Tab: Authorization
  Type: Bearer Token
  Token: [paste your token]

Tab: Body
  Select: form-data
  
  Add field:
    Key: image
    Type: File (change from Text)
    Value: [Click to select an image file from your computer]

Click: Send
```

**You'll see**:
```json
{
  "message": "Image uploaded successfully",
  "image_url": "/media/hotel_images/1/abc123def456.jpg",
  "hotel_id": 1,
  "hotel_images": [
    "/media/hotel_images/1/abc123def456.jpg"
  ]
}
```

✅ **The image is saved and added to your hotel!**

---

### Step 3: Upload More Images (Repeat Step 2)

Every time you upload, the image URL is automatically added to your hotel's images array:

```json
{
  "image_url": "/media/hotel_images/1/new_image.jpg",
  "hotel_images": [
    "/media/hotel_images/1/abc123def456.jpg",
    "/media/hotel_images/1/new_image.jpg"
  ]
}
```

---

### Step 4: Get Your Hotel with All Images

In Postman:

```
GET http://localhost:8000/api/hotel/

Tab: Authorization
  Type: Bearer Token
  Token: [your token]

Send
```

**Response includes all your uploaded images**:
```json
{
  "message": "Hotel retrieved successfully",
  "hotel": {
    "id": 1,
    "hotel_name": "My Hotel",
    "images": [
      "/media/hotel_images/1/abc123def456.jpg",
      "/media/hotel_images/1/new_image.jpg"
    ],
    "amenities": [],
    ...
  }
}
```

---

## 📺 Visual Postman Setup

### Uploading an Image

```
┌─────────────────────────────────────────────────────┐
│ POST http://localhost:8000/api/hotel/upload-image/  │
└─────────────────────────────────────────────────────┘

┌─ Authorization ─┐
│ Type: Bearer Token
│ Token: [paste access token]
└────────────────┘

┌─ Body ────────────────┐
│ ◉ form-data
│ ○ raw
│ ○ binary
│
│ Key        | Type  | Value
│ ───────────┼───────┼──────────────
│ image      | File  | [select file]
└────────────────────────┘

[ Send ] → 200 OK
```

---

## 🖼️ Complete Example Flow

### Scenario: Upload 3 hotel images

**Request 1: Upload Image 1**
```
POST /api/hotel/upload-image/
form-data:
  image: hotel-front.jpg

Response:
{
  "message": "Image uploaded successfully",
  "image_url": "/media/hotel_images/1/img1.jpg",
  "hotel_images": ["/media/hotel_images/1/img1.jpg"]
}
```

**Request 2: Upload Image 2**
```
POST /api/hotel/upload-image/
form-data:
  image: hotel-lobby.jpg

Response:
{
  "message": "Image uploaded successfully",
  "image_url": "/media/hotel_images/1/img2.jpg",
  "hotel_images": [
    "/media/hotel_images/1/img1.jpg",
    "/media/hotel_images/1/img2.jpg"
  ]
}
```

**Request 3: Upload Image 3**
```
POST /api/hotel/upload-image/
form-data:
  image: hotel-pool.jpg

Response:
{
  "message": "Image uploaded successfully",
  "image_url": "/media/hotel_images/1/img3.jpg",
  "hotel_images": [
    "/media/hotel_images/1/img1.jpg",
    "/media/hotel_images/1/img2.jpg",
    "/media/hotel_images/1/img3.jpg"
  ]
}
```

**Now GET your hotel**:
```
GET /api/hotel/

Response:
{
  "hotel": {
    "id": 1,
    "images": [
      "/media/hotel_images/1/img1.jpg",
      "/media/hotel_images/1/img2.jpg",
      "/media/hotel_images/1/img3.jpg"
    ]
  }
}
```

---

## ✅ Checklist Before Uploading

- [ ] You have your Bearer token
- [ ] You're logged in as a **partner** account
- [ ] Your image is JPEG, PNG, GIF, or WebP
- [ ] Your image is **less than 5 MB**
- [ ] You selected the file correctly in Postman

---

## 🐛 Common Issues

### Issue: "No image file provided"

**Problem**: You sent the form incorrectly

**Fix**:
1. Make sure `Body` is set to **form-data**
2. Change the field Type from **Text** to **File**
3. Click to select an actual image file
4. Don't leave the Value field empty

### Issue: "File size exceeds maximum limit"

**Problem**: Your image is larger than 5 MB

**Solution**:
- Use an image under 5 MB
- Compress the image using online tools
- Or resize the image to smaller dimensions

### Issue: "Invalid image format"

**Problem**: Your file type is not supported

**Solution**:
- Use JPEG, PNG, GIF, or WebP only
- If you have BMP or TIFF, convert to PNG or JPEG
- Online converters: cloudconvert.com, convertio.co

### Issue: 401 Unauthorized

**Problem**: Your token is wrong or expired

**Fix**:
1. Go back to `/api/token/` endpoint
2. Get a fresh token
3. Paste it in Authorization tab
4. Try again

### Issue: 403 Forbidden

**Problem**: You're not a partner account

**Fix**:
- Make sure you're using a partner account username
- Partner accounts auto-create hotels
- Contact admin to verify your account type

---

## 📋 API Endpoints

### Upload Image
```
POST /api/hotel/upload-image/

Required:
  - Authorization header with Bearer token
  - form-data with "image" field containing file

Returns:
  200 OK:
    {
      "message": "Image uploaded successfully",
      "image_url": "/media/hotel_images/1/uuid.jpg",
      "hotel_id": 1,
      "hotel_images": [...]
    }

  400 Bad Request:
    - Missing image file
    - File too large (>5MB)
    - Invalid format

  403 Forbidden:
    - Not a partner account

  404 Not Found:
    - Hotel not found
```

### Get Hotel (includes images)
```
GET /api/hotel/

Returns:
  {
    "hotel": {
      "images": [
        "/media/hotel_images/1/uuid1.jpg",
        "/media/hotel_images/1/uuid2.jpg"
      ],
      ...
    }
  }
```

### Update Hotel (if needed)
```
PATCH /api/hotel/

Body (JSON):
  {
    "amenities": ["WiFi", "Pool"],
    "hotel_name": "My Hotel"
  }

Images are already stored from uploads!
```

---

## 🎥 What Happens When You Upload

```
1. You select image in Postman
   ↓
2. Postman sends it as multipart/form-data
   ↓
3. Server receives and validates:
   - Is it an image? ✓
   - Is it < 5MB? ✓
   - Is format supported? ✓
   ↓
4. Server saves to: media/hotel_images/1/uuid.jpg
   ↓
5. Server generates URL: /media/hotel_images/1/uuid.jpg
   ↓
6. Server adds URL to hotel.images array
   ↓
7. Server returns response with image_url
   ↓
8. Image is now accessible at: 
   http://localhost:8000/media/hotel_images/1/uuid.jpg
```

---

## 🚀 Ready to Upload?

1. Get your token from `/api/token/`
2. Open new Postman request
3. Set method to **POST**
4. Set URL to `http://localhost:8000/api/hotel/upload-image/`
5. Add Bearer token in Authorization
6. Set Body to **form-data**
7. Add field: Key=`image`, Type=**File**, Value=[select image]
8. Click **Send**
9. ✅ Done! Image is uploaded and added to your hotel

---

## 📸 Supported Image Formats

| Format | Extension | Status |
|--------|-----------|--------|
| JPEG | .jpg, .jpeg | ✅ |
| PNG | .png | ✅ |
| GIF | .gif | ✅ |
| WebP | .webp | ✅ |
| BMP | .bmp | ❌ |
| TIFF | .tiff | ❌ |
| SVG | .svg | ❌ |

---

## 💡 Pro Tips

1. **Upload many images**: Just repeat the POST request for each image
2. **Organize by hotel**: Files are automatically organized by hotel ID
3. **URLs are unique**: Each image gets a unique filename
4. **Accessible immediately**: After upload, images are ready to use
5. **No manual URL entry**: URLs are auto-added to images array

---

## ✨ Summary

**Old Way**: Send image URLs as strings  
**New Way**: Upload files → Auto-saved and added to array ✅

**Endpoint**: `POST /api/hotel/upload-image/`  
**Method**: form-data with image file  
**Result**: Image URL automatically added to hotel.images  
**Status**: Ready to use! 🎉
