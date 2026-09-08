"""Blueprint route packages for kvk-appt."""

from .admin import admin_bp
from .api import api_bp
from .public import public_bp
from .superadmin import superadmin_bp

__all__ = ["admin_bp", "api_bp", "public_bp", "superadmin_bp"]
