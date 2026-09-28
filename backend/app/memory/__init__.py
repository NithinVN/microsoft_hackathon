"""IncidentMind Hindsight Memory Module.

Provides integration with Hindsight Cloud / Hindsight API for persistent
organizational memory (retain, recall, reflect).
"""

from backend.app.memory.hindsight_service import HindsightService, hindsight_service

__all__ = ["HindsightService", "hindsight_service"]
