# home/permissions.py

import hmac
import logging

from django.conf import settings
from rest_framework.permissions import BasePermission
from rest_framework.exceptions import PermissionDenied

logger = logging.getLogger(__name__)


class IsN8nRequest(BasePermission):
    """
    بررسی توکن n8n با مقایسه امن (ضد Timing Attack).
    """

    def has_permission(self, request, view):
        token = request.headers.get('X-N8N-TOKEN', '')

        if not token:
            logger.warning(
                "N8n API request without token from %s",
                request.META.get('REMOTE_ADDR', 'unknown'),
            )
            raise PermissionDenied('X-N8N-TOKEN header required.')

        expected = getattr(settings, 'N8N_SECRET_TOKEN', '')
        if not expected:
            logger.error("N8N_SECRET_TOKEN not configured in settings!")
            raise PermissionDenied('Server configuration error.')

        # ✅ مقایسه امن — ضد Timing Attack
        if not hmac.compare_digest(token.encode(), expected.encode()):
            logger.warning(
                "Invalid N8n token from %s",
                request.META.get('REMOTE_ADDR', 'unknown'),
            )
            raise PermissionDenied('Invalid N8N token.')

        return True
