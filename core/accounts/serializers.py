from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from .models import TravelerProfile, PartnerProfile, PasswordResetOTP, TravelerInfo, PartnerInfo
from django.utils import timezone
from datetime import timedelta


class LoginSerializer(serializers.Serializer):
    """Login with email and password"""
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})

    def validate(self, data):
        email = data.get('email')
        password = data.get('password')

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError("Invalid email or password")

        # Authenticate with username
        user_auth = authenticate(username=user.username, password=password)
        if not user_auth:
            raise serializers.ValidationError("Invalid email or password")

        data['user'] = user_auth
        return data


class TravelerProfileSerializer(serializers.ModelSerializer):
    """Serializer for traveler profile - GET requests"""
    profile_picture_url = serializers.SerializerMethodField()
    user_email = serializers.CharField(source='user.email', read_only=True)
    user_first_name = serializers.CharField(source='user.first_name', read_only=True)
    user_last_name = serializers.CharField(source='user.last_name', read_only=True)
    
    class Meta:
        model = TravelerProfile
        fields = ['profile_type', 'bio', 'profile_picture', 'profile_picture_url', 
                  'user_email', 'user_first_name', 'user_last_name', 'created_at', 'updated_at']
        read_only_fields = ['profile_type', 'created_at', 'updated_at']
    
    def get_profile_picture_url(self, obj):
        """Get full URL for profile picture"""
        if obj.profile_picture:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.profile_picture.url)
        return None


class TravelerProfileUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating traveler profile - PATCH requests"""
    class Meta:
        model = TravelerProfile
        fields = ['bio', 'profile_picture']
    
    def update(self, instance, validated_data):
        """Update traveler profile"""
        instance.bio = validated_data.get('bio', instance.bio)
        if 'profile_picture' in validated_data:
            instance.profile_picture = validated_data['profile_picture']
        instance.save()
        return instance


class UserRegistrationSerializer(serializers.Serializer):
    """Traveler Registration - Simplified (no username needed)"""
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    password_confirm = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    full_name = serializers.CharField(max_length=255, required=True)

    def validate(self, data):
        if data['password'] != data.pop('password_confirm'):
            raise serializers.ValidationError("Passwords do not match!")
        
        if User.objects.filter(email=data['email']).exists():
            raise serializers.ValidationError("Email already exists!")
        
        return data

    def create(self, validated_data):
        email = validated_data['email']
        # Generate username from email (before @)
        username = email.split('@')[0]
        
        # If username already exists, append a number
        if User.objects.filter(username=username).exists():
            counter = 1
            while User.objects.filter(username=f"{username}{counter}").exists():
                counter += 1
            username = f"{username}{counter}"
        
        # Split full_name into first_name and last_name
        full_name = validated_data['full_name'].strip()
        name_parts = full_name.split(' ', 1)
        first_name = name_parts[0] if len(name_parts) > 0 else ''
        last_name = name_parts[1] if len(name_parts) > 1 else ''
        
        user = User.objects.create_user(
            username=username,
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=first_name[:150],
            last_name=last_name[:150]
        )
        
        # Create traveler profile automatically
        TravelerProfile.objects.create(user=user, profile_type='traveler')
        
        return user


class PartnerProfileSerializer(serializers.ModelSerializer):
    profile_picture_url = serializers.SerializerMethodField()
    
    class Meta:
        model = PartnerProfile
        fields = ['profile_type', 'property_name', 'property_address', 'website_url', 
                  'contact_person_name', 'phone_number', 'role', 'special_deals_offers', 'profile_picture', 'profile_picture_url']
        read_only_fields = ['profile_type']
    
    def get_profile_picture_url(self, obj):
        """Get full URL for profile picture"""
        if obj.profile_picture:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.profile_picture.url)
            return obj.profile_picture.url
        return None
    
    def to_representation(self, instance):
        """Add base URL to profile_picture field"""
        data = super().to_representation(instance)
        request = self.context.get('request')
        
        if data.get('profile_picture') and request:
            base_url = request.build_absolute_uri('/')
            profile_pic = data['profile_picture']
            if not profile_pic.startswith('http'):
                data['profile_picture'] = f"{base_url.rstrip('/')}{profile_pic}"
        
        return data


class PartnerProfileUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating partner profile (PATCH)"""
    profile_picture_url = serializers.SerializerMethodField()
    
    class Meta:
        model = PartnerProfile
        fields = ['property_name', 'property_address', 'website_url', 
                  'contact_person_name', 'phone_number', 'role', 'special_deals_offers', 'profile_picture', 'profile_picture_url']
        extra_kwargs = {
            'property_name': {'required': False},
            'property_address': {'required': False},
            'contact_person_name': {'required': False},
            'phone_number': {'required': False},
            'role': {'required': False},
        }
    
    def get_profile_picture_url(self, obj):
        """Get full URL for profile picture"""
        if obj.profile_picture:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.profile_picture.url)
            return obj.profile_picture.url
        return None
    
    def to_representation(self, instance):
        """Add base URL to profile_picture field"""
        data = super().to_representation(instance)
        request = self.context.get('request')
        
        if data.get('profile_picture') and request:
            base_url = request.build_absolute_uri('/')
            profile_pic = data['profile_picture']
            if not profile_pic.startswith('http'):
                data['profile_picture'] = f"{base_url.rstrip('/')}{profile_pic}"
        
        return data


class PartnerRegistrationStep1Serializer(serializers.Serializer):
    """Step 1: Property Information"""
    property_name = serializers.CharField(max_length=255, required=True)
    property_address = serializers.CharField(required=True)
    website_url = serializers.URLField(required=False, allow_blank=True)


class PartnerRegistrationStep2Serializer(serializers.ModelSerializer):
    """Step 2: Contact & Account Setup"""
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    password_confirm = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'password_confirm']

    def validate(self, data):
        if data['password'] != data.pop('password_confirm'):
            raise serializers.ValidationError("Passwords do not match!")
        return data


class PartnerRegistrationCompleteSerializer(serializers.Serializer):
    """Complete Partner Registration - Simplified (no username needed)"""
    # Property Info
    property_name = serializers.CharField(max_length=255, required=True)
    property_address = serializers.CharField(required=True)
    website_url = serializers.URLField(required=False, allow_blank=True)
    
    # Contact & Setup
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    password_confirm = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    contact_person_name = serializers.CharField(max_length=255, required=True)
    phone_number = serializers.CharField(max_length=20, required=True)
    role = serializers.ChoiceField(choices=PartnerProfile.ROLE_CHOICES)

    def validate(self, data):
        if data['password'] != data.pop('password_confirm'):
            raise serializers.ValidationError("Passwords do not match!")
        
        if User.objects.filter(email=data['email']).exists():
            raise serializers.ValidationError("Email already exists!")
        
        return data

    def create(self, validated_data):
        # Extract partner-specific data
        email = validated_data['email']
        property_name = validated_data.pop('property_name')
        property_address = validated_data.pop('property_address')
        website_url = validated_data.pop('website_url', '')
        contact_person_name = validated_data.pop('contact_person_name')
        phone_number = validated_data.pop('phone_number')
        role = validated_data.pop('role')
        
        # Generate username from email (before @)
        username = email.split('@')[0]
        
        # If username already exists, append a number
        if User.objects.filter(username=username).exists():
            counter = 1
            while User.objects.filter(username=f"{username}{counter}").exists():
                counter += 1
            username = f"{username}{counter}"

        # Create user
        user = User.objects.create_user(
            username=username,
            email=validated_data['email'],
            password=validated_data['password'],
        )

        # Create partner profile
        PartnerProfile.objects.create(
            user=user,
            profile_type='partner',
            property_name=property_name,
            property_address=property_address,
            website_url=website_url,
            contact_person_name=contact_person_name,
            phone_number=phone_number,
            role=role,
            special_deals_offers=False  # Default to False
        )

        return user


class ForgotPasswordSerializer(serializers.Serializer):
    """Request OTP for password reset"""
    email = serializers.EmailField(required=True)

    def validate_email(self, value):
        try:
            User.objects.get(email=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("Email not found in the system")
        return value


class VerifyOTPSerializer(serializers.Serializer):
    """Verify OTP sent to email"""
    email = serializers.EmailField(required=True)
    otp = serializers.CharField(max_length=6, min_length=6, required=True)

    def validate(self, data):
        email = data['email']
        otp = data['otp']

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError("Email not found")

        try:
            otp_record = PasswordResetOTP.objects.get(user=user, email=email)
        except PasswordResetOTP.DoesNotExist:
            raise serializers.ValidationError("No OTP found for this email. Request a new one.")

        if not otp_record.is_valid():
            raise serializers.ValidationError("OTP has expired or already verified")

        if otp_record.otp != otp:
            raise serializers.ValidationError("Invalid OTP")

        data['user'] = user
        return data


class ResetPasswordSerializer(serializers.Serializer):
    """Reset password after OTP verification"""
    email = serializers.EmailField(required=True)
    otp = serializers.CharField(max_length=6, min_length=6, required=True)
    new_password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    confirm_password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})

    def validate(self, data):
        email = data['email']
        otp = data['otp']
        new_password = data['new_password']
        confirm_password = data.pop('confirm_password')

        if new_password != confirm_password:
            raise serializers.ValidationError("Passwords do not match!")

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError("Email not found")

        try:
            otp_record = PasswordResetOTP.objects.get(user=user, email=email)
        except PasswordResetOTP.DoesNotExist:
            raise serializers.ValidationError("No OTP found. Please request password reset first.")

        if not otp_record.is_valid():
            raise serializers.ValidationError("OTP has expired or already verified")

        if otp_record.otp != otp:
            raise serializers.ValidationError("Invalid OTP")

        data['user'] = user
        data['otp_record'] = otp_record
        return data


class ChangePasswordSerializer(serializers.Serializer):
    """Change password for authenticated users (requires current password)"""
    current_password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    new_password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    confirm_password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})

    def validate(self, data):
        new_password = data['new_password']
        confirm_password = data.pop('confirm_password')

        if new_password != confirm_password:
            raise serializers.ValidationError("New passwords do not match!")

        return data


class TravelerInfoSerializer(serializers.ModelSerializer):
    """Serializer for TravelerInfo - Read and Update"""
    class Meta:
        model = TravelerInfo
        fields = ['id', 'title', 'description', 'terms_and_conditions', 'privacy_policy', 'updated_at']
        read_only_fields = ['id', 'updated_at']


class PartnerInfoSerializer(serializers.ModelSerializer):
    """Serializer for PartnerInfo - Read and Update"""
    class Meta:
        model = PartnerInfo
        fields = ['id', 'title', 'description', 'terms_and_conditions', 'privacy_policy', 'commission_info', 'updated_at']
        read_only_fields = ['id', 'updated_at']


class UserDetailSerializer(serializers.ModelSerializer):
    """Detailed user serializer for admin viewing individual users"""
    traveler_profile = TravelerProfileSerializer(read_only=True)
    partner_profile = PartnerProfileSerializer(read_only=True)
    profile_type = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'is_active', 'is_staff', 'is_superuser', 
                  'date_joined', 'last_login', 'profile_type', 'traveler_profile', 'partner_profile']
        read_only_fields = ['id', 'date_joined', 'last_login']
    
    def get_profile_type(self, obj):
        """Determine user profile type"""
        if obj.is_superuser or obj.is_staff:
            return 'admin'
        elif hasattr(obj, 'traveler_profile'):
            return 'traveler'
        elif hasattr(obj, 'partner_profile'):
            return 'partner'
        return 'unknown'


class UserListSerializer(serializers.ModelSerializer):
    """Simplified user serializer for listing users with admin"""
    profile_type = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'is_active', 'is_staff', 
                  'is_superuser', 'date_joined', 'profile_type']
        read_only_fields = fields
    
    def get_profile_type(self, obj):
        """Determine user profile type"""
        if obj.is_superuser or obj.is_staff:
            return 'admin'
        elif hasattr(obj, 'traveler_profile'):
            return 'traveler'
        elif hasattr(obj, 'partner_profile'):
            return 'partner'
        return 'unknown'
