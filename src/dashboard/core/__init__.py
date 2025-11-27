"""Core application wiring (Flask app, API registration)."""

from .app import app, server  # noqa: F401

__all__ = ["app", "server"]
