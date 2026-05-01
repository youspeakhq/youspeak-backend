"""
Arena Service Models.
Re-exports models from the core app to maintain consistency during Phase 1.
"""

import sys
import os

# Ensure app/ is in path if running locally
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from app.models.arena import Arena, ArenaParticipant, ArenaStatus
    from app.models.user import User
except ImportError:
    # Fallback for when app/ is not available (e.g. during standalone testing)
    # In production Docker, PYTHONPATH should include /app
    raise ImportError("Core models not found. Ensure PYTHONPATH includes the project root.")

__all__ = [
    "Arena",
    "ArenaParticipant",
    "ArenaStatus",
    "User",
]
