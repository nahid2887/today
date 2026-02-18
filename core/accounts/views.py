from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import IsAuthenticated, BasePermission
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from .serializers import (
    UserRegistrationSerializer, 
    PartnerRegistrationStep1Serializer,
    PartnerRegistrationStep2Serializer,
    PartnerRegistrationCompleteSerializer,
    PartnerProfileSerializer,
    PartnerProfileUpdateSerializer,
    TravelerProfileSerializer,
    TravelerProfileUpdateSerializer,
    LoginSerializer,
    ForgotPasswordSerializer,
    VerifyOTPSerializer,
    ResetPasswordSerializer,
    ChangePasswordSerializer,
    TravelerInfoSerializer,
    PartnerInfoSerializer,
    UserListSerializer,
    UserDetailSerializer
)
from rest_framework.pagination import PageNumberPagination
from .models import PasswordResetOTP, TravelerInfo, PartnerInfo
from django.utils import timezone
from datetime import timedelta
from django.core.mail import send_mail
from django.conf import settings


class IsSuperAdmin(BasePermission):
    """
    Allows access only to superadmin users.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_superuser)


class UserRegistrationView(APIView):
    """
    Register a new traveler user and create traveler profile.
    Returns access token, refresh token, and user information.
    """
    
    @extend_schema(
        request=UserRegistrationSerializer,
        responses={201: OpenApiResponse(description="User registered successfully with tokens")},
        tags=['Authentication'],
        description="Register a new Traveler account"
    )
    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        
        if serializer.is_valid():
            user = serializer.save()
            
            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            access = refresh.access_token
            
            # Combine first_name and last_name into full_name
            full_name = f"{user.first_name} {user.last_name}".strip()
            
            return Response({
                'message': 'User registered successfully',
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'full_name': full_name,
                },
                'access_token': str(access),
                'refresh_token': str(refresh),
                'profile': {
                    'profile_type': user.traveler_profile.profile_type,
                }
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PartnerRegistrationStep1View(APIView):
    """
    Partner Registration - Step 1: Property Information
    Validates property details
    """
    
    @extend_schema(
        request=PartnerRegistrationStep1Serializer,
        responses={200: OpenApiResponse(description="Step 1 validated successfully")},
        tags=['Partner Registration'],
        description="Step 1: Validate property information"
    )
    def post(self, request):
        serializer = PartnerRegistrationStep1Serializer(data=request.data)
        
        if serializer.is_valid():
            return Response({
                'message': 'Step 1 validated. Proceed to Step 2',
                'step': 1,
                'data': serializer.validated_data
            }, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PartnerRegistrationStep2View(APIView):
    """
    Partner Registration - Step 2: Contact & Account Setup
    Validates contact and account credentials
    """
    
    @extend_schema(
        request=PartnerRegistrationStep2Serializer,
        responses={200: OpenApiResponse(description="Step 2 validated successfully")},
        tags=['Partner Registration'],
        description="Step 2: Validate contact and account setup"
    )
    def post(self, request):
        serializer = PartnerRegistrationStep2Serializer(data=request.data)
        
        if serializer.is_valid():
            return Response({
                'message': 'Step 2 validated. Ready to create account',
                'step': 2,
                'data': {
                    'username': serializer.validated_data['username'],
                    'email': serializer.validated_data['email']
                }
            }, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PartnerRegistrationView(APIView):
    """
    Complete Partner Registration (Both Steps)
    Register a new partner user and create partner profile.
    Returns access token, refresh token, and partner information.
    """
    
    @extend_schema(
        request=PartnerRegistrationCompleteSerializer,
        responses={201: OpenApiResponse(description="Partner account created successfully with tokens")},
        tags=['Partner Registration'],
        description="Register a new Partner account with all required information"
    )
    def post(self, request):
        serializer = PartnerRegistrationCompleteSerializer(data=request.data)
        
        if serializer.is_valid():
            user = serializer.save()
            
            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            access = refresh.access_token
            
            partner_profile = user.partner_profile
            
            return Response({
                'message': 'Partner account created successfully',
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                },
                'access_token': str(access),
                'refresh_token': str(refresh),
                'profile': {
                    'profile_type': partner_profile.profile_type,
                    'property_name': partner_profile.property_name,
                    'property_address': partner_profile.property_address,
                    'website_url': partner_profile.website_url,
                    'contact_person_name': partner_profile.contact_person_name,
                    'phone_number': partner_profile.phone_number,
                    'role': partner_profile.role,
                    'special_deals_offers': partner_profile.special_deals_offers,
                }
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserLoginView(APIView):
    """
    Login user (Traveler or Partner) with email and password.
    Returns access token and refresh token.
    """
    
    @extend_schema(
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'email': {'type': 'string', 'description': 'Email address'},
                    'password': {'type': 'string', 'description': 'Password'}
                },
                'required': ['email', 'password']
            }
        },
        responses={200: OpenApiResponse(description="Login successful")},
        tags=['Authentication'],
        description="Login with email and password"
    )
    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')
        
        if not email or not password:
            return Response({
                'error': 'Email and password are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get user by email
        try:
            user_obj = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({
                'error': 'Invalid credentials'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # Authenticate with username
        user = authenticate(username=user_obj.username, password=password)
        
        if user is None:
            return Response({
                'error': 'Invalid credentials'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        access = refresh.access_token
        
        # Determine profile type
        profile_type = 'unknown'
        profile_data = {}
        
        # Check if user is superuser/admin
        if user.is_superuser or user.is_staff:
            profile_type = 'admin'
            profile_data = {'profile_type': 'admin', 'is_staff': user.is_staff, 'is_superuser': user.is_superuser}
        elif hasattr(user, 'traveler_profile'):
            profile_type = 'traveler'
            profile_data = {'profile_type': user.traveler_profile.profile_type}
        elif hasattr(user, 'partner_profile'):
            profile_type = 'partner'
            partner = user.partner_profile
            profile_data = {
                'profile_type': partner.profile_type,
                'property_name': partner.property_name,
                'role': partner.role,
            }
        
        # Combine first_name and last_name into full_name
        full_name = f"{user.first_name} {user.last_name}".strip()
        
        return Response({
            'message': 'Login successful',
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'full_name': full_name,
                'profile_type': profile_type,
            },
            'access_token': str(access),
            'refresh_token': str(refresh),
            'profile': profile_data
        }, status=status.HTTP_200_OK)


class EmailLoginView(APIView):
    """
    Login user with email and password.
    Works for both Traveler and Partner accounts.
    Returns access token and refresh token.
    """
    
    @extend_schema(
        request=LoginSerializer,
        responses={200: OpenApiResponse(description="Email login successful")},
        tags=['Authentication'],
        description="Login with email and password"
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        
        if serializer.is_valid():
            user = serializer.validated_data['user']
            
            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            access = refresh.access_token
            
            # Determine profile type
            profile_type = 'unknown'
            profile_data = {}
            
            if hasattr(user, 'traveler_profile'):
                profile_type = 'traveler'
                profile_data = {
                    'profile_type': user.traveler_profile.profile_type,
                }
            elif hasattr(user, 'partner_profile'):
                profile_type = 'partner'
                partner = user.partner_profile
                profile_data = {
                    'profile_type': partner.profile_type,
                    'property_name': partner.property_name,
                    'property_address': partner.property_address,
                    'contact_person_name': partner.contact_person_name,
                    'phone_number': partner.phone_number,
                    'role': partner.role,
                }
            
            return Response({
                'message': 'Login successful',
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'profile_type': profile_type,
                },
                'access_token': str(access),
                'refresh_token': str(refresh),
                'profile': profile_data
            }, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ForgotPasswordView(APIView):
    """
    Request password reset OTP.
    Sends OTP to the provided email address.
    Works for both Traveler and Partner accounts.
    """
    
    @extend_schema(
        request=ForgotPasswordSerializer,
        responses={200: OpenApiResponse(description="OTP sent to email")},
        tags=['Password Reset'],
        description="Request OTP for password reset"
    )
    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        
        if serializer.is_valid():
            email = serializer.validated_data['email']
            
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                return Response({
                    'error': 'Email not found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Generate OTP
            otp = PasswordResetOTP.generate_otp()
            expires_at = timezone.now() + timedelta(minutes=10)
            
            # Create or update OTP record
            otp_record, created = PasswordResetOTP.objects.update_or_create(
                user=user,
                defaults={
                    'otp': otp,
                    'email': email,
                    'expires_at': expires_at,
                    'is_verified': False
                }
            )
            
            # Send OTP via email
            subject = 'Password Reset OTP - Tri2'
            message = f"""
Hello {user.first_name or user.username},

You have requested to reset your password. Please use the following One-Time Password (OTP) to proceed:

    OTP: {otp}

This OTP is valid for 10 minutes only.

If you did not request this, please ignore this email and your password will remain unchanged.

Best regards,
Tri2 Team
            """
            
            try:
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[email],
                    fail_silently=False,
                )
                email_sent = True
            except Exception as e:
                print(f"Error sending email: {str(e)}")
                email_sent = False
            
            # For testing - also print OTP to console
            print(f"\n{'='*50}")
            print(f"PASSWORD RESET OTP FOR: {email}")
            print(f"OTP: {otp}")
            print(f"Valid for 10 minutes")
            print(f"{'='*50}\n")
            
            return Response({
                'message': 'OTP sent to your email' if email_sent else 'OTP generated (email may have failed)',
                'email': email,
                'otp_valid_minutes': 10,
                'email_sent': email_sent,
            }, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class VerifyOTPView(APIView):
    """
    Verify OTP sent to email.
    Required before resetting password.
    """
    
    @extend_schema(
        request=VerifyOTPSerializer,
        responses={200: OpenApiResponse(description="OTP verified successfully")},
        tags=['Password Reset'],
        description="Verify OTP for password reset"
    )
    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        
        if serializer.is_valid():
            user = serializer.validated_data['user']
            email = serializer.validated_data['email']
            
            try:
                otp_record = PasswordResetOTP.objects.get(user=user, email=email)
            except PasswordResetOTP.DoesNotExist:
                return Response({
                    'error': 'OTP record not found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Mark OTP as verified
            otp_record.is_verified = True
            otp_record.save()
            
            return Response({
                'message': 'OTP verified successfully',
                'email': email,
                'verified': True
            }, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ResetPasswordView(APIView):
    """
    Reset password with verified OTP.
    Can only reset password after OTP verification.
    Works for both Traveler and Partner accounts.
    """
    
    @extend_schema(
        request=ResetPasswordSerializer,
        responses={200: OpenApiResponse(description="Password reset successfully")},
        tags=['Password Reset'],
        description="Reset password with verified OTP"
    )
    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        
        if serializer.is_valid():
            user = serializer.validated_data['user']
            otp_record = serializer.validated_data['otp_record']
            new_password = serializer.validated_data['new_password']
            
            # Update password
            user.set_password(new_password)
            user.save()
            
            # Delete OTP record after successful reset
            otp_record.delete()
            
            return Response({
                'message': 'Password reset successfully',
                'email': user.email,
                'username': user.username
            }, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ChangePasswordView(APIView):
    """
    Change password for authenticated users.
    Requires current password verification.
    Works for both Traveler and Partner accounts.
    """
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        request=ChangePasswordSerializer,
        responses={200: OpenApiResponse(description="Password changed successfully")},
        tags=['Password Management'],
        description="Change password for authenticated user (requires current password)"
    )
    def post(self, request):
        user = request.user
        serializer = ChangePasswordSerializer(data=request.data)
        
        if serializer.is_valid():
            current_password = serializer.validated_data['current_password']
            new_password = serializer.validated_data['new_password']
            
            # Verify current password
            if not user.check_password(current_password):
                return Response({
                    'error': 'Current password is incorrect'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Update password
            user.set_password(new_password)
            user.save()
            
            return Response({
                'message': 'Password changed successfully',
                'email': user.email,
                'username': user.username
            }, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PartnerProfileView(APIView):
    """
    GET: Retrieve partner profile (own profile only)
    PATCH: Update partner profile including profile picture (own profile only)
    """
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        responses={200: PartnerProfileSerializer},
        tags=['Partner Profile'],
        description="Get authenticated partner's profile"
    )
    def get(self, request):
        user = request.user
        
        # Check if user has a partner profile
        if not hasattr(user, 'partner_profile'):
            return Response({
                'error': 'Partner profile not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        partner_profile = user.partner_profile
        serializer = PartnerProfileSerializer(partner_profile, context={'request': request})
        
        return Response({
            'message': 'Partner profile retrieved successfully',
            'profile': serializer.data
        }, status=status.HTTP_200_OK)
    
    @extend_schema(
        request=PartnerProfileUpdateSerializer,
        responses={200: PartnerProfileSerializer},
        tags=['Partner Profile'],
        description="Update authenticated partner's profile (including profile picture)"
    )
    def patch(self, request):
        user = request.user
        
        # Check if user has a partner profile
        if not hasattr(user, 'partner_profile'):
            return Response({
                'error': 'Partner profile not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        partner_profile = user.partner_profile
        serializer = PartnerProfileUpdateSerializer(
            partner_profile, 
            data=request.data, 
            partial=True,
            context={'request': request}
        )
        
        if serializer.is_valid():
            serializer.save()
            
            # Return updated profile
            updated_serializer = PartnerProfileSerializer(partner_profile, context={'request': request})
            
            return Response({
                'message': 'Partner profile updated successfully',
                'profile': updated_serializer.data
            }, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TravelerProfileView(APIView):
    """
    GET: Retrieve traveler profile (own profile only)
    PATCH: Update traveler profile including profile picture (own profile only)
    """
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        responses={200: TravelerProfileSerializer},
        tags=['Traveler Profile'],
        description="Get authenticated traveler's profile"
    )
    def get(self, request):
        user = request.user
        
        # Check if user has a traveler profile
        if not hasattr(user, 'traveler_profile'):
            return Response({
                'message': 'Traveler profile not found',
                'status': 'error'
            }, status=status.HTTP_404_NOT_FOUND)
        
        traveler_profile = user.traveler_profile
        serializer = TravelerProfileSerializer(traveler_profile, context={'request': request})
        
        return Response({
            'message': 'Traveler profile retrieved successfully',
            'profile': serializer.data
        }, status=status.HTTP_200_OK)
    
    @extend_schema(
        request={'application/json': {'type': 'object', 'properties': {'bio': {'type': 'string'}, 'profile_picture': {'type': 'string', 'format': 'binary'}}}},
        responses={200: TravelerProfileSerializer},
        tags=['Traveler Profile'],
        description="Update authenticated traveler's profile (including profile picture)"
    )
    def patch(self, request):
        user = request.user
        
        # Check if user has a traveler profile
        if not hasattr(user, 'traveler_profile'):
            return Response({
                'message': 'Traveler profile not found',
                'status': 'error'
            }, status=status.HTTP_404_NOT_FOUND)
        
        traveler_profile = user.traveler_profile
        serializer = TravelerProfileUpdateSerializer(
            traveler_profile, 
            data=request.data, 
            partial=True,
            context={'request': request}
        )
        
        if serializer.is_valid():
            serializer.save()
            
            # Return updated profile
            updated_serializer = TravelerProfileSerializer(traveler_profile, context={'request': request})
            
            return Response({
                'message': 'Traveler profile updated successfully',
                'profile': updated_serializer.data
            }, status=status.HTTP_200_OK)
        
        return Response({
            'message': 'Validation error',
            'errors': serializer.errors,
            'status': 'error'
        }, status=status.HTTP_400_BAD_REQUEST)


class TravelerTermsView(APIView):
    """
    GET: Retrieve traveler terms & conditions (publicly accessible)
    PATCH: Update traveler terms & conditions (admin only)
    """
    
    @extend_schema(
        responses={200: OpenApiResponse(description="Traveler terms & conditions retrieved")},
        tags=['Traveler Info'],
        description="Get traveler terms & conditions (publicly accessible - no authentication required)"
    )
    def get(self, request):
        # Get or create the singleton instance
        traveler_info, created = TravelerInfo.objects.get_or_create(id=1)
        
        return Response({
            'message': 'Traveler terms & conditions retrieved successfully',
            'terms_and_conditions': traveler_info.terms_and_conditions or '',
            'updated_at': traveler_info.updated_at
        }, status=status.HTTP_200_OK)
    
    @extend_schema(
        request={'application/json': {'type': 'object', 'properties': {'terms_and_conditions': {'type': 'string'}}}},
        responses={200: OpenApiResponse(description="Traveler terms & conditions updated")},
        tags=['Traveler Info'],
        description="Update traveler terms & conditions (admin only)"
    )
    def patch(self, request):
        user = request.user
        
        # Check if user is authenticated and is admin
        if not user.is_authenticated or not user.is_staff:
            return Response({
                'error': 'Access denied. Only admins can update this information.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        traveler_info, created = TravelerInfo.objects.get_or_create(id=1)
        traveler_info.terms_and_conditions = request.data.get('terms_and_conditions', traveler_info.terms_and_conditions)
        traveler_info.save()
        
        return Response({
            'message': 'Traveler terms & conditions updated successfully',
            'terms_and_conditions': traveler_info.terms_and_conditions,
            'updated_at': traveler_info.updated_at
        }, status=status.HTTP_200_OK)


class TravelerPrivacyView(APIView):
    """
    GET: Retrieve traveler privacy policy (publicly accessible)
    PATCH: Update traveler privacy policy (admin only)
    """
    
    @extend_schema(
        responses={200: OpenApiResponse(description="Traveler privacy policy retrieved")},
        tags=['Traveler Info'],
        description="Get traveler privacy policy (publicly accessible - no authentication required)"
    )
    def get(self, request):
        # Get or create the singleton instance
        traveler_info, created = TravelerInfo.objects.get_or_create(id=1)
        
        return Response({
            'message': 'Traveler privacy policy retrieved successfully',
            'privacy_policy': traveler_info.privacy_policy or '',
            'updated_at': traveler_info.updated_at
        }, status=status.HTTP_200_OK)
    
    @extend_schema(
        request={'application/json': {'type': 'object', 'properties': {'privacy_policy': {'type': 'string'}}}},
        responses={200: OpenApiResponse(description="Traveler privacy policy updated")},
        tags=['Traveler Info'],
        description="Update traveler privacy policy (admin only)"
    )
    def patch(self, request):
        user = request.user
        
        # Check if user is authenticated and is admin
        if not user.is_authenticated or not user.is_staff:
            return Response({
                'error': 'Access denied. Only admins can update this information.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        traveler_info, created = TravelerInfo.objects.get_or_create(id=1)
        traveler_info.privacy_policy = request.data.get('privacy_policy', traveler_info.privacy_policy)
        traveler_info.save()
        
        return Response({
            'message': 'Traveler privacy policy updated successfully',
            'privacy_policy': traveler_info.privacy_policy,
            'updated_at': traveler_info.updated_at
        }, status=status.HTTP_200_OK)


class PartnerTermsView(APIView):
    """
    GET: Retrieve partner terms & conditions (for partners)
    PATCH: Update partner terms & conditions (admin only)
    """
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        responses={200: OpenApiResponse(description="Partner terms & conditions retrieved")},
        tags=['Partner Info'],
        description="Get partner terms & conditions (accessible by partners)"
    )
    def get(self, request):
        user = request.user
        
        # Check if user is a partner
        if not hasattr(user, 'partner_profile'):
            return Response({
                'error': 'Access denied. Only partners can view this information.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Get or create the singleton instance
        partner_info, created = PartnerInfo.objects.get_or_create(id=1)
        
        return Response({
            'message': 'Partner terms & conditions retrieved successfully',
            'terms_and_conditions': partner_info.terms_and_conditions or '',
            'updated_at': partner_info.updated_at
        }, status=status.HTTP_200_OK)
    
    @extend_schema(
        request={'application/json': {'type': 'object', 'properties': {'terms_and_conditions': {'type': 'string'}}}},
        responses={200: OpenApiResponse(description="Partner terms & conditions updated")},
        tags=['Partner Info'],
        description="Update partner terms & conditions (admin only)"
    )
    def patch(self, request):
        user = request.user
        
        # Check if user is admin
        if not user.is_staff:
            return Response({
                'error': 'Access denied. Only admins can update this information.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        partner_info, created = PartnerInfo.objects.get_or_create(id=1)
        partner_info.terms_and_conditions = request.data.get('terms_and_conditions', partner_info.terms_and_conditions)
        partner_info.save()
        
        return Response({
            'message': 'Partner terms & conditions updated successfully',
            'terms_and_conditions': partner_info.terms_and_conditions,
            'updated_at': partner_info.updated_at
        }, status=status.HTTP_200_OK)


class PartnerPrivacyView(APIView):
    """
    GET: Retrieve partner privacy policy (for partners)
    PATCH: Update partner privacy policy (admin only)
    """
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        responses={200: OpenApiResponse(description="Partner privacy policy retrieved")},
        tags=['Partner Info'],
        description="Get partner privacy policy (accessible by partners)"
    )
    def get(self, request):
        user = request.user
        
        # Check if user is a partner
        if not hasattr(user, 'partner_profile'):
            return Response({
                'error': 'Access denied. Only partners can view this information.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Get or create the singleton instance
        partner_info, created = PartnerInfo.objects.get_or_create(id=1)
        
        return Response({
            'message': 'Partner privacy policy retrieved successfully',
            'privacy_policy': partner_info.privacy_policy or '',
            'updated_at': partner_info.updated_at
        }, status=status.HTTP_200_OK)
    
    @extend_schema(
        request={'application/json': {'type': 'object', 'properties': {'privacy_policy': {'type': 'string'}}}},
        responses={200: OpenApiResponse(description="Partner privacy policy updated")},
        tags=['Partner Info'],
        description="Update partner privacy policy (admin only)"
    )
    def patch(self, request):
        user = request.user
        
        # Check if user is admin
        if not user.is_staff:
            return Response({
                'error': 'Access denied. Only admins can update this information.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        partner_info, created = PartnerInfo.objects.get_or_create(id=1)
        partner_info.privacy_policy = request.data.get('privacy_policy', partner_info.privacy_policy)
        partner_info.save()
        
        return Response({
            'message': 'Partner privacy policy updated successfully',
            'privacy_policy': partner_info.privacy_policy,
            'updated_at': partner_info.updated_at
        }, status=status.HTTP_200_OK)


class UserPagination(PageNumberPagination):
    """Pagination class for user list"""
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class UserManagementListView(APIView):
    """
    GET: List all users with filtering, search, and pagination (superadmin only)
    Query Parameters:
    - role: Filter by role (traveler, partner, admin, unknown)
    - search: Search by username, email, first_name, or last_name
    - page: Page number for pagination (default: 1)
    - page_size: Number of items per page (default: 10, max: 100)
    """
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name='role',
                description='Filter by user role: traveler, partner, admin, unknown',
                required=False,
                type=str,
                enum=['traveler', 'partner', 'admin', 'unknown']
            ),
            OpenApiParameter(
                name='search',
                description='Search by username, email, first_name, or last_name',
                required=False,
                type=str
            ),
            OpenApiParameter(
                name='page',
                description='Page number for pagination (default: 1)',
                required=False,
                type=int
            ),
            OpenApiParameter(
                name='page_size',
                description='Number of items per page (default: 10, max: 100)',
                required=False,
                type=int
            ),
        ],
        responses={200: OpenApiResponse(description="List of users with pagination")},
        tags=['User Management'],
        description="List all users with filtering, search, and pagination (superadmin only)"
    )
    def get(self, request):
        # Get filter and search parameters
        role_filter = request.query_params.get('role', None)
        search_query = request.query_params.get('search', None)

        # Start with all users
        users = User.objects.all().order_by('-date_joined')

        # Apply search filter
        if search_query:
            from django.db.models import Q
            users = users.filter(
                Q(username__icontains=search_query) |
                Q(email__icontains=search_query) |
                Q(first_name__icontains=search_query) |
                Q(last_name__icontains=search_query)
            )

        # Apply role filter
        if role_filter:
            if role_filter == 'admin':
                users = users.filter(is_superuser=True)
            elif role_filter == 'traveler':
                # Get user IDs that have traveler profiles
                traveler_user_ids = TravelerProfile.objects.values_list('user_id', flat=True)
                users = users.filter(id__in=traveler_user_ids)
            elif role_filter == 'partner':
                # Get user IDs that have partner profiles
                partner_user_ids = PartnerProfile.objects.values_list('user_id', flat=True)
                users = users.filter(id__in=partner_user_ids)

        # Get total count
        total_count = users.count()

        # Apply pagination
        paginator = UserPagination()
        paginated_users = paginator.paginate_queryset(users, request)

        # Serialize data
        serializer = UserListSerializer(paginated_users, many=True)

        return Response({
            'message': 'Users retrieved successfully',
            'total_count': total_count,
            'count': len(paginated_users),
            'next': paginator.get_next_link(),
            'previous': paginator.get_previous_link(),
            'page_size': paginator.page_size,
            'current_page': paginator.page_number if hasattr(paginator, 'page_number') else 1,
            'results': serializer.data
        }, status=status.HTTP_200_OK)


class UserDetailManagementView(APIView):
    """
    GET: Retrieve detailed information about a specific user (superadmin only)
    DELETE: Delete a user account (superadmin only)
    """
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    @extend_schema(
        responses={200: OpenApiResponse(description="User details retrieved successfully")},
        tags=['User Management'],
        description="Get detailed information about a specific user (superadmin only)"
    )
    def get(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({
                'error': 'User not found'
            }, status=status.HTTP_404_NOT_FOUND)

        serializer = UserDetailSerializer(user)

        return Response({
            'message': 'User details retrieved successfully',
            'user': serializer.data
        }, status=status.HTTP_200_OK)

    @extend_schema(
        responses={204: OpenApiResponse(description="User deleted successfully")},
        tags=['User Management'],
        description="Delete a user account (superadmin only)"
    )
    def delete(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({
                'error': 'User not found'
            }, status=status.HTTP_404_NOT_FOUND)

        # Prevent deleting the superadmin making the request
        if user.id == request.user.id:
            return Response({
                'error': 'Cannot delete your own account'
            }, status=status.HTTP_400_BAD_REQUEST)

        username = user.username
        email = user.email

        # Delete the user (this will cascade delete related profiles)
        user.delete()

        return Response({
            'message': 'User deleted successfully',
            'deleted_user': {
                'id': user_id,
                'username': username,
                'email': email
            }
        }, status=status.HTTP_200_OK)

