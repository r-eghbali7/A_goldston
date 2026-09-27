import hmac
import logging

from django.conf import settings
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission

logger = logging.getLogger(__name__)


class IsN8nRequest(BasePermission):
    """
    Permission class for N8N webhook requests.
    Requires X-N8N-TOKEN header with valid token.
    Uses constant-time comparison to prevent timing attacks.
    """

    def has_permission(self, request, view):
        token = request.headers.get("X-N8N-TOKEN")

        if not token:
            logger.warning(
                "N8N API access attempt without token from IP: %s",
                request.META.get("REMOTE_ADDR"),
            )
            raise PermissionDenied("توکن احراز هویت الزامی است.")

        expected_token = getattr(settings, "N8N_SECRET_TOKEN", "")

        if not expected_token:
            logger.error("N8N_SECRET_TOKEN is not configured in settings.")
            raise PermissionDenied("خطای پیکربندی سرور.")

        if not hmac.compare_digest(token, expected_token):
            logger.warning(
                "Invalid N8N token attempt from IP: %s",
                request.META.get("REMOTE_ADDR"),
            )
            raise PermissionDenied("توکن نامعتبر است.")

        return True
