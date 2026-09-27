import hashlib
import hmac

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class PhoneNumberBackend(ModelBackend):
    """
    Authentication backend using phone_number instead of username.
    - Handles lockout check
    - Registers failed attempts
    - Resets on success
    """

    def authenticate(self, request, phone_number=None, password=None, **kwargs):
        if phone_number is None or password is None:
            return None

        UserModel = get_user_model()

        try:
            user = UserModel.objects.get(phone_number=phone_number)
        except UserModel.DoesNotExist:
            # ⬇ Constant-time dummy check to prevent timing attacks
            UserModel().set_password(password)
            return None

        # Account lockout check
        if user.is_locked_out():
            return None

        # Password verification
        if not user.check_password(password):
            user.register_failed_attempt()
            return None

        # Inactive user
        if not user.is_active:
            return None

        # Success → reset counters
        user.reset_failed_attempts()
        return user

    def get_user(self, user_id):
        UserModel = get_user_model()
        try:
            return UserModel.objects.get(pk=user_id)
        except UserModel.DoesNotExist:
            return None
