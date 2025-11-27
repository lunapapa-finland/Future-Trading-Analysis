"""
Compatibility shim for legacy imports.

The main Flask app lives in dashboard.core.app; this module re-exports it so
existing imports of `dashboard.app` continue to work.
"""

from dashboard.core.app import app, server  # noqa: F401

__all__ = ["app", "server"]
