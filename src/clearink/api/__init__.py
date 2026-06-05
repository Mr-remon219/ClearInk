"""ClearInk API layer — bridge between core logic and web frontend.

Provides session management and stateless API functions that
encapsulate the full ClearInk workflow (query, follow-up, step
mode, mode switching).  Designed for direct use from Django views.

Usage (Django example)::

    from clearink.api import query, followup

    def paper_query_view(request):
        result = query(
            paper=request.POST["paper"],
            second_input=request.POST.get("formula", ""),
            mode=1,
            session_id=request.session.session_key,
        )
        return JsonResponse(result)
"""

from .session import Session, SessionManager, get_session_manager
from .endpoints import (
    query,
    followup,
    step_next,
    step_end,
    set_mode,
    set_step_mode,
    get_session_info,
    delete_session,
)

__all__ = [
    "Session",
    "SessionManager",
    "get_session_manager",
    "query",
    "followup",
    "step_next",
    "step_end",
    "set_mode",
    "set_step_mode",
    "get_session_info",
    "delete_session",
]
