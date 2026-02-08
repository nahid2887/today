from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    UserRegistrationView, 
    UserLoginView,
    EmailLoginView,
    PartnerRegistrationStep1View,
    PartnerRegistrationStep2View,
    PartnerRegistrationView,
    PartnerProfileView,
    ForgotPasswordView,
    VerifyOTPView,
    ResetPasswordView,
    ChangePasswordView,
    TravelerTermsView,
    TravelerPrivacyView,
    PartnerTermsView,
    PartnerPrivacyView
)

app_name = 'accounts'

urlpatterns = [
    # Traveler Authentication
    path('register/', UserRegistrationView.as_view(), name='traveler_register'),
    path('login/', UserLoginView.as_view(), name='login'),
    path('login/email/', EmailLoginView.as_view(), name='email_login'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # Password Management
    path('forgot-password/', ForgotPasswordView.as_view(), name='forgot_password'),
    path('verify-otp/', VerifyOTPView.as_view(), name='verify_otp'),
    path('reset-password/', ResetPasswordView.as_view(), name='reset_password'),
    path('change-password/', ChangePasswordView.as_view(), name='change_password'),
    
    # Partner Registration
    path('partner/register/step1/', PartnerRegistrationStep1View.as_view(), name='partner_register_step1'),
    path('partner/register/step2/', PartnerRegistrationStep2View.as_view(), name='partner_register_step2'),
    path('partner/register/', PartnerRegistrationView.as_view(), name='partner_register'),
    
    # Partner Profile Management
    path('partner/profile/', PartnerProfileView.as_view(), name='partner_profile'),
    
    # Traveler Information Endpoints
    path('traveler/terms/', TravelerTermsView.as_view(), name='traveler_terms'),
    path('traveler/privacy/', TravelerPrivacyView.as_view(), name='traveler_privacy'),
    
    # Partner Information Endpoints
    path('partner/terms/', PartnerTermsView.as_view(), name='partner_terms'),
    path('partner/privacy/', PartnerPrivacyView.as_view(), name='partner_privacy'),
]
