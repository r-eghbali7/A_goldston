from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from coineshop.views import profile

app_name = 'accounts'

urlpatterns = [

    # ================= Auth =================
    path('register/', views.register, name='register'),
    path('login/', views.custom_login, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # ================= OTP =================
    path('otp/verify/', views.otp_verification, name='otp_verify'),
    path("otp/resend/", views.otp_resend, name="otp_resend"),
    
    # ================= Profile =================
    path('profile/', profile, name='profile'),

    # ================= Password Change =================
    path('password/change/',auth_views.PasswordChangeView.as_view(template_name='registration/password_change_form.html'),name='password_change'),
    path('password/change/done/',auth_views.PasswordChangeDoneView.as_view(template_name='registration/password_change_done.html'),name='password_change_done'),

    # ================= Password Reset =================
    path("password/reset/phone/", views.password_reset_phone, name="password_reset_phone"),
    path("password/reset/otp/", views.password_reset_otp, name="password_reset_otp"),
    path("password/reset/confirm/", views.password_reset_confirm, name="password_reset_confirm"),
    path('password/reset/complete/',auth_views.PasswordResetCompleteView.as_view(template_name='registration/password_reset_complete.html'),name='password_reset_complete'),
]
