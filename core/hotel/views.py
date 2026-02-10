from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.parsers import MultiPartParser, FormParser
from drf_spectacular.utils import extend_schema, OpenApiResponse
from .models import Hotel, SpecialOffer
from .serializers import (
    HotelSerializer, HotelUpdateSerializer, HotelListSerializer,
    SpecialOfferSerializer, SpecialOfferListSerializer, HotelDetailSerializer,
    HotelBulkSyncSerializer, HotelRealTimeDetailSerializer
)
import os
from django.conf import settings


class HotelView(APIView):
    """
    GET: Retrieve hotel(s)
         - Partners: Get their own hotel (auto-created on account creation)
         - Others: Get all approved hotels
    PATCH: Update hotel (Partner only)
           Supports both JSON and form-data (with image uploads)
           Sets is_approved to 'pending' for admin review
    """
    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser)  # Support form-data and file uploads
    
    @extend_schema(
        responses={200: HotelListSerializer(many=True)},
        tags=['Hotel'],
        description="Get hotel - Partners get their own, others get approved hotels"
    )
    def get(self, request):
        user = request.user
        
        # Check if user is a partner
        if hasattr(user, 'partner_profile'):
            # Partner gets their own hotel
            try:
                hotel = Hotel.objects.get(partner=user)
                serializer = HotelSerializer(hotel)
                
                # Convert image paths to full URLs
                hotel_data = serializer.data
                if hotel_data.get('images'):
                    base_url = request.build_absolute_uri('/').rstrip('/')
                    hotel_data['images'] = [
                        f"{base_url}{img}" if img.startswith('/') else img 
                        for img in hotel_data['images']
                    ]
                
                return Response({
                    'message': 'Hotel retrieved successfully',
                    'hotel': hotel_data
                }, status=status.HTTP_200_OK)
            except Hotel.DoesNotExist:
                return Response({
                    'message': 'No hotel found. Hotel should be auto-created with your partner account.',
                    'hotel': None
                }, status=status.HTTP_404_NOT_FOUND)
        else:
            # Travelers and admins get all approved hotels
            hotels = Hotel.objects.filter(is_approved='approved')
            serializer = HotelListSerializer(hotels, many=True)
            
            # Convert image paths to full URLs for all hotels
            hotels_data = serializer.data
            base_url = request.build_absolute_uri('/').rstrip('/')
            for hotel_data in hotels_data:
                if hotel_data.get('images'):
                    hotel_data['images'] = [
                        f"{base_url}{img}" if img.startswith('/') else img 
                        for img in hotel_data['images']
                    ]
            
            return Response({
                'message': f'{hotels.count()} approved hotels found',
                'hotels': hotels_data
            }, status=status.HTTP_200_OK)
    
    @extend_schema(
        request=HotelUpdateSerializer,
        responses={200: HotelSerializer},
        tags=['Hotel'],
        description="Update hotel information - Supports JSON and form-data with image uploads"
    )
    def patch(self, request):
        user = request.user
        
        # Check if user is a partner
        if not hasattr(user, 'partner_profile'):
            return Response({
                'error': 'Only partners can update hotels'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Get partner's hotel
        try:
            hotel = Hotel.objects.get(partner=user)
        except Hotel.DoesNotExist:
            return Response({
                'error': 'No hotel found. Your hotel should have been auto-created.'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Handle image uploads if present (both 'image' and 'images' field names)
        uploaded_image_urls = []
        image_files = []
        
        # Check for images in request.FILES
        if 'images' in request.FILES:
            image_files = request.FILES.getlist('images')
        elif 'image' in request.FILES:
            image_files = request.FILES.getlist('image')
        
        if image_files:
            for image_file in image_files:
                # Validate file size
                max_size = getattr(settings, 'MAX_UPLOAD_SIZE', 5242880)  # 5MB
                if image_file.size > max_size:
                    return Response({
                        'error': f'File {image_file.name} exceeds maximum size of {max_size / 1024 / 1024}MB'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # Validate file type
                allowed_types = getattr(settings, 'ALLOWED_IMAGE_TYPES', ['image/jpeg', 'image/png', 'image/gif', 'image/webp'])
                if image_file.content_type not in allowed_types:
                    return Response({
                        'error': f'Invalid image format for {image_file.name}. Allowed: {", ".join(allowed_types)}'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # Create directory
                media_root = settings.MEDIA_ROOT
                hotel_images_dir = os.path.join(media_root, 'hotel_images', str(hotel.id))
                os.makedirs(hotel_images_dir, exist_ok=True)
                
                # Generate unique filename
                import uuid
                file_ext = os.path.splitext(image_file.name)[1]
                unique_filename = f"{uuid.uuid4()}{file_ext}"
                file_path = os.path.join(hotel_images_dir, unique_filename)
                
                # Save file
                try:
                    with open(file_path, 'wb+') as destination:
                        for chunk in image_file.chunks():
                            destination.write(chunk)
                    
                    image_url = f"/media/hotel_images/{hotel.id}/{unique_filename}"
                    uploaded_image_urls.append(image_url)
                    
                except Exception as e:
                    return Response({
                        'error': f'Failed to save {image_file.name}: {str(e)}'
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # Prepare data for serializer (exclude file fields)
        data = {}
        # Copy only non-file fields to avoid serializer validation errors
        for key, value in request.data.items():
            if key not in ['image', 'images']:  # Skip file field keys
                data[key] = value
        
        # Handle images separately
        if uploaded_image_urls:
            existing_images = hotel.images or []
            # Add new images, avoiding duplicates
            for url in uploaded_image_urls:
                if url not in existing_images:
                    existing_images.append(url)
            data['images'] = existing_images
        
        serializer = HotelUpdateSerializer(hotel, data=data, partial=True)
        
        if serializer.is_valid():
            hotel = serializer.save()
            
            # Prepare response with full URLs
            hotel_data = HotelSerializer(hotel).data
            
            # Convert image paths to full URLs
            if hotel_data.get('images'):
                base_url = request.build_absolute_uri('/').rstrip('/')
                hotel_data['images'] = [
                    f"{base_url}{img}" if img.startswith('/') else img 
                    for img in hotel_data['images']
                ]
            
            response_message = 'Hotel updated successfully. Status set to pending for admin review.'
            if uploaded_image_urls:
                response_message += f' Uploaded {len(uploaded_image_urls)} image(s).'
            
            return Response({
                'message': response_message,
                'hotel': hotel_data
            }, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



class SpecialOfferView(APIView):
    """
    POST: Create a special offer (Partner only, for their hotel)
    GET: List special offers
         - Partners: Get all their hotel's offers
         - Others: Get all active offers for approved hotels
    """
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        responses={200: SpecialOfferListSerializer(many=True)},
        tags=['Special Offers'],
        description="List special offers - Partners see all their offers, others see active offers"
    )
    def get(self, request):
        user = request.user
        
        # Check if user is a partner
        if hasattr(user, 'partner_profile'):
            # Partner gets all their hotel's offers
            try:
                hotel = Hotel.objects.get(partner=user)
                offers = SpecialOffer.objects.filter(hotel=hotel)
                serializer = SpecialOfferListSerializer(offers, many=True)
                return Response({
                    'message': f'{offers.count()} special offers found',
                    'offers': serializer.data
                }, status=status.HTTP_200_OK)
            except Hotel.DoesNotExist:
                return Response({
                    'message': 'No hotel found. Create your hotel first.',
                    'offers': []
                }, status=status.HTTP_404_NOT_FOUND)
        else:
            # Others get active offers for approved hotels only
            from django.utils import timezone
            offers = SpecialOffer.objects.filter(
                hotel__is_approved='approved',
                is_active=True,
                valid_until__gte=timezone.now().date()
            )
            serializer = SpecialOfferListSerializer(offers, many=True)
            return Response({
                'message': f'{offers.count()} active special offers found',
                'offers': serializer.data
            }, status=status.HTTP_200_OK)
    
    @extend_schema(
        request=SpecialOfferSerializer,
        responses={201: SpecialOfferSerializer},
        tags=['Special Offers'],
        description="Create a special offer (Partner only)"
    )
    def post(self, request):
        user = request.user
        
        # Check if user is a partner
        if not hasattr(user, 'partner_profile'):
            return Response({
                'error': 'Only partners can create special offers'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Get partner's hotel
        try:
            hotel = Hotel.objects.get(partner=user)
        except Hotel.DoesNotExist:
            return Response({
                'error': 'No hotel found. Create a hotel first.'
            }, status=status.HTTP_404_NOT_FOUND)
        
        serializer = SpecialOfferSerializer(data=request.data)
        
        if serializer.is_valid():
            # Set the hotel to the partner's hotel
            offer = serializer.save(hotel=hotel)
            
            return Response({
                'message': 'Special offer created successfully',
                'offer': SpecialOfferSerializer(offer).data
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SpecialOfferDetailView(APIView):
    """
    GET: Retrieve a specific special offer
    PATCH: Update a special offer (Partner only, their own offers)
    """
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        responses={200: SpecialOfferSerializer},
        tags=['Special Offers'],
        description="Get a specific special offer by ID"
    )
    def get(self, request, pk):
        try:
            offer = SpecialOffer.objects.get(pk=pk)
            
            # Check permissions
            user = request.user
            if hasattr(user, 'partner_profile'):
                # Partner can view their own offers
                try:
                    hotel = Hotel.objects.get(partner=user)
                    if offer.hotel != hotel:
                        return Response({
                            'error': 'You can only view your own hotel offers'
                        }, status=status.HTTP_403_FORBIDDEN)
                except Hotel.DoesNotExist:
                    return Response({
                        'error': 'No hotel found'
                    }, status=status.HTTP_404_NOT_FOUND)
            else:
                # Others can only view active offers for approved hotels
                if not (offer.is_active and offer.hotel.is_approved == 'approved'):
                    return Response({
                        'error': 'Offer not found or not available'
                    }, status=status.HTTP_404_NOT_FOUND)
            
            serializer = SpecialOfferSerializer(offer)
            return Response({
                'message': 'Special offer retrieved successfully',
                'offer': serializer.data
            }, status=status.HTTP_200_OK)
            
        except SpecialOffer.DoesNotExist:
            return Response({
                'error': 'Special offer not found'
            }, status=status.HTTP_404_NOT_FOUND)
    
    @extend_schema(
        request=SpecialOfferSerializer,
        responses={200: SpecialOfferSerializer},
        tags=['Special Offers'],
        description="Update a special offer (Partner only)"
    )
    def patch(self, request, pk):
        user = request.user
        
        # Check if user is a partner
        if not hasattr(user, 'partner_profile'):
            return Response({
                'error': 'Only partners can update special offers'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Get partner's hotel
        try:
            hotel = Hotel.objects.get(partner=user)
        except Hotel.DoesNotExist:
            return Response({
                'error': 'No hotel found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Get the offer
        try:
            offer = SpecialOffer.objects.get(pk=pk)
        except SpecialOffer.DoesNotExist:
            return Response({
                'error': 'Special offer not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Verify ownership
        if offer.hotel != hotel:
            return Response({
                'error': 'You can only update your own hotel offers'
            }, status=status.HTTP_403_FORBIDDEN)
        
        serializer = SpecialOfferSerializer(offer, data=request.data, partial=True)
        
        if serializer.is_valid():
            serializer.save()
            
            return Response({
                'message': 'Special offer updated successfully',
                'offer': SpecialOfferSerializer(offer).data
            }, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class HotelDetailView(APIView):
    """
    GET: Retrieve detailed hotel information with special offers
    """
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        responses={200: HotelDetailSerializer},
        tags=['Hotel'],
        description="Get detailed hotel information including active special offers"
    )
    def get(self, request, pk):
        """
        Get hotel details with active special offers
        Only approved hotels are visible to non-partners
        """
        try:
            hotel = Hotel.objects.get(pk=pk)
            
            # Check if user is the hotel owner or if hotel is approved
            user = request.user
            is_owner = hasattr(user, 'partner_profile') and hotel.partner == user
            
            if not is_owner and hotel.is_approved != 'approved':
                return Response({
                    'error': 'Hotel not found or not available'
                }, status=status.HTTP_404_NOT_FOUND)
            
            serializer = HotelDetailSerializer(hotel)
            return Response({
                'message': 'Hotel details retrieved successfully',
                'hotel': serializer.data
            }, status=status.HTTP_200_OK)
            
        except Hotel.DoesNotExist:
            return Response({
                'error': 'Hotel not found'
            }, status=status.HTTP_404_NOT_FOUND)


class HotelBulkSyncView(APIView):
    """
    GET: Bulk sync endpoint for RAG system
    Purpose: Provides all static hotel information used for embeddings.
    Data: hotel_id, hotel_name, description, location_details, amenities, etc.
    Note: Includes last_updated timestamp for incremental updates via cron job
    """
    permission_classes = [AllowAny]  # Allow AI system to access without auth
    
    @extend_schema(
        responses={200: HotelBulkSyncSerializer(many=True)},
        tags=['AI System'],
        description="Bulk sync endpoint for RAG system - Returns all approved hotels with static data"
    )
    def get(self, request):
        """
        Get all approved hotels with static information for RAG embeddings.
        Supports optional 'since' parameter for incremental syncs.
        """
        # Get all approved hotels
        hotels = Hotel.objects.filter(is_approved='approved').order_by('id')
        
        # Optional: Filter by last_updated timestamp for incremental syncs
        since = request.query_params.get('since')
        if since:
            try:
                from django.utils import timezone
                from datetime import datetime
                since_datetime = datetime.fromisoformat(since)
                hotels = hotels.filter(updated_at__gte=since_datetime)
            except (ValueError, TypeError):
                pass  # Ignore invalid timestamp format
        
        serializer = HotelBulkSyncSerializer(hotels, many=True)
        hotels_data = serializer.data
        
        # Convert image paths to full URLs
        base_url = request.build_absolute_uri('/').rstrip('/')
        for hotel in hotels_data:
            if 'images' in hotel and hotel['images']:
                hotel['images'] = [f"{base_url}{img}" if not img.startswith('http') else img for img in hotel['images']]
        
        return Response({
            'message': f'Synced {hotels.count()} approved hotels',
            'count': hotels.count(),
            'hotels': hotels_data
        }, status=status.HTTP_200_OK)


class HotelRealTimeDetailView(APIView):
    """
    GET: Real-time detail endpoint for AI verification
    Purpose: Returns volatile data (prices, availability, offers) for on-the-fly verification.
    Data: base_price_per_night, active_special_offers, commission_tier, current_availability
    Note: Must be high-performance as AI calls this during chat to verify current state
    """
    permission_classes = [AllowAny]  # Allow AI system to access without auth
    
    @extend_schema(
        responses={200: HotelRealTimeDetailSerializer},
        tags=['AI System'],
        description="Real-time detail endpoint for AI verification - Returns current prices and offers"
    )
    def get(self, request, hotel_id):
        """
        Get real-time hotel details for AI verification.
        Only returns approved hotels to prevent outdated information from being served.
        """
        try:
            hotel = Hotel.objects.get(id=hotel_id, is_approved='approved')
            serializer = HotelRealTimeDetailSerializer(hotel)
            
            return Response({
                'message': 'Hotel details retrieved successfully',
                'hotel': serializer.data
            }, status=status.HTTP_200_OK)
            
        except Hotel.DoesNotExist:
            return Response({
                'error': 'Hotel not found or not approved',
                'hotel_id': hotel_id
            }, status=status.HTTP_404_NOT_FOUND)


class HotelImageUploadView(APIView):
    """
    Upload hotel images
    POST: Upload a single image file
    """
    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser)
    
    @extend_schema(
        request=None,
        responses={200: {'description': 'Image uploaded successfully'}},
        tags=['Hotel'],
        description="Upload an image file for hotel - Returns image URL to add to images array"
    )
    def post(self, request):
        user = request.user
        
        # Check if user is a partner
        if not hasattr(user, 'partner_profile'):
            return Response({
                'error': 'Only partners can upload hotel images'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Get partner's hotel
        try:
            hotel = Hotel.objects.get(partner=user)
        except Hotel.DoesNotExist:
            return Response({
                'error': 'No hotel found. Your hotel should have been auto-created.'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check if image file is provided
        if 'image' not in request.FILES:
            return Response({
                'error': 'No image file provided. Use "image" as the form field name.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        image_file = request.FILES['image']
        
        # Validate file size (max 5MB)
        max_size = getattr(settings, 'MAX_UPLOAD_SIZE', 5242880)
        if image_file.size > max_size:
            return Response({
                'error': f'File size exceeds maximum limit of {max_size / 1024 / 1024}MB'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate file type
        allowed_types = getattr(settings, 'ALLOWED_IMAGE_TYPES', ['image/jpeg', 'image/png', 'image/gif', 'image/webp'])
        if image_file.content_type not in allowed_types:
            return Response({
                'error': f'Invalid image format. Allowed formats: {", ".join(allowed_types)}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create media directory if it doesn't exist
        media_root = settings.MEDIA_ROOT
        hotel_images_dir = os.path.join(media_root, 'hotel_images', str(hotel.id))
        os.makedirs(hotel_images_dir, exist_ok=True)
        
        # Generate unique filename
        import uuid
        file_ext = os.path.splitext(image_file.name)[1]
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        file_path = os.path.join(hotel_images_dir, unique_filename)
        
        # Save file
        try:
            with open(file_path, 'wb+') as destination:
                for chunk in image_file.chunks():
                    destination.write(chunk)
        except Exception as e:
            return Response({
                'error': f'Failed to save image: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # Generate URL
        image_url = f"/media/hotel_images/{hotel.id}/{unique_filename}"
        
        # Add image URL to hotel's images array
        if image_url not in hotel.images:
            hotel.images.append(image_url)
            hotel.save()
        
        return Response({
            'message': 'Image uploaded successfully',
            'image_url': image_url,
            'hotel_id': hotel.id,
            'hotel_images': hotel.images
        }, status=status.HTTP_200_OK)
