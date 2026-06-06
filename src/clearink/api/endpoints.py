"""Public API functions for the ClearInk API layer.

Every function is a plain Python callable that returns a ``dict``
suitable for JSON serialisation.  Django views call these directly;
no HTTP concern leaks into this module.
"""

from __future__ import annotations

from clearink.message import extract_text_from_content
from clearink.user import mode as mode_mod

from .session import get_session_manager
from .web_format import format_browser_response


# ── Helpers ──────────────────────────────────────────────────

def agent_loop(messages: list) -> list:
    """Lazy proxy for the main runtime loop.

    Importing ``clearink.main`` registers tools and reads runtime env files, so
    keep that work out of plain ``clearink.api`` imports.  Django views can
    import this module cheaply, and the full runtime is loaded only when a
    request actually needs model execution.
    """
    from clearink.main import agent_loop as main_agent_loop

    return main_agent_loop(messages)


def _extract_response(messages: list) -> str | None:
    """Walk *messages* in reverse to find the last assistant text."""
    for msg in reversed(messages):
        if msg.get("role") != "assistant":
            continue
        content = msg.get("content")
        text = extract_text_from_content(content).strip()
        if text:
            return text
    return None


def _make_user_message(text: str, current_mode: int) -> dict:
    """Wrap *text* with the current mode instructions as a prefix."""
    mode_prompt = mode_mod.get_mode_prompt(current_mode)
    if mode_prompt:
        prefixed = (
            f"[Mode {current_mode} instructions begin]\n"
            f"{mode_prompt}\n"
            f"[Mode {current_mode} instructions end]\n\n"
            f"{text}"
        )
    else:
        prefixed = text
    return {"role": "user", "content": prefixed}


def _ok(**kwargs) -> dict:
    data = dict(kwargs)
    data["ok"] = True
    return data


def _err(message: str) -> dict:
    return {"ok": False, "error": message}


# ── Public API ───────────────────────────────────────────────

def query(
    paper: str,
    second_input: str = "",
    mode: int = 1,
    session_id: str | None = None,
) -> dict:
    """Execute a first paper query (equivalent to CLI paper title + formula).

    Creates a new session (or resets an existing one) and runs the
    initial query through ``agent_loop``.

    Args:
        paper:        Paper title or identifier.
        second_input: Formula number, description, or question
                      (mode-dependent).
        mode:         1 = formula analysis, 2 = paper Q&A.
        session_id:   Optional existing session ID.  A new one is
                      generated if omitted.

    Returns:
        ``{"ok": True, "session_id": ..., "response": ..., ...}``
        or ``{"ok": False, "error": "..."}``.
    """
    if mode not in (mode_mod.MODE_1, mode_mod.MODE_2):
        return _err(f"Invalid mode: {mode}. Use 1 or 2.")

    try:
        mgr = get_session_manager()
        sess = mgr.get_or_create(session_id) if session_id else mgr.create()
        with sess.lock:
            query_text = mode_mod.build_query_for_mode(paper, second_input, mode)
            sess.reset(
                [{"role": "user", "content": query_text}],
                mode=mode,
                step_mode=False,
            )

            messages = agent_loop(sess.messages)
            sess.messages = messages
            mgr.touch(sess.session_id)

            raw = _extract_response(messages) or "(no response)"
            response = format_browser_response(raw)
            messages_count = len(messages)

        return _ok(
            session_id=sess.session_id,
            response=response,
            mode=mode,
            messages_count=messages_count,
        )
    except Exception as e:
        return _err(str(e))


def followup(text: str, session_id: str) -> dict:
    """Send a follow-up question in an existing session.

    Args:
        text:       The follow-up question.
        session_id: An existing session ID (from ``query()``).

    Returns:
        ``{"ok": True, "response": "...", ...}``
        or ``{"ok": False, "error": "..."}``.
    """
    mgr = get_session_manager()
    sess = mgr.get(session_id)
    if sess is None:
        return _err(f"Session '{session_id}' not found.  Start with query() first.")

    try:
        with sess.lock:
            msg = _make_user_message(text, sess.mode)

            # Inject step-mode instructions if active
            if sess.step_mode:
                msg["content"] = (
                    mode_mod.build_step_instructions() + "\n\n" + msg["content"]
                )

            sess.messages.append(msg)
            messages = agent_loop(sess.messages)
            sess.messages = messages
            mgr.touch(session_id)

            raw = _extract_response(messages) or "(no response)"
            response = format_browser_response(raw)
            current_mode = sess.mode
            current_step_mode = sess.step_mode
            messages_count = len(messages)

        return _ok(
            session_id=session_id,
            response=response,
            mode=current_mode,
            step_mode=current_step_mode,
            messages_count=messages_count,
        )
    except Exception as e:
        return _err(str(e))


def step_next(session_id: str) -> dict:
    """Step mode: continue to the next step.

    Appends a continuation marker and calls ``agent_loop``.
    """
    mgr = get_session_manager()
    sess = mgr.get(session_id)
    if sess is None:
        return _err(f"Session '{session_id}' not found.")

    try:
        with sess.lock:
            sess.messages.append({"role": "user", "content": "[继续下一步]"})
            messages = agent_loop(sess.messages)
            sess.messages = messages
            mgr.touch(session_id)

            raw = _extract_response(messages) or "(no response)"
            response = format_browser_response(raw)
            messages_count = len(messages)

        return _ok(
            session_id=session_id,
            response=response,
            messages_count=messages_count,
        )
    except Exception as e:
        return _err(str(e))


def step_end(session_id: str) -> dict:
    """Step mode: end the current round.

    Does NOT clear messages — just signals the frontend that the
    round is complete.  A new ``query()`` or ``followup()`` can
    be called next.
    """
    mgr = get_session_manager()
    sess = mgr.get(session_id)
    if sess is None:
        return _err(f"Session '{session_id}' not found.")

    with sess.lock:
        mgr.touch(session_id)
        messages_count = len(sess.messages)

    return _ok(
        session_id=session_id,
        message="本轮结束，请输入新问题。",
        messages_count=messages_count,
    )


def set_mode(mode: int, session_id: str) -> dict:
    """Switch the active mode for a session.

    Args:
        mode:       1 or 2.
        session_id: Session ID.

    Returns:
        ``{"ok": True, "mode": N}`` or error.
    """
    if mode not in (1, 2):
        return _err(f"Invalid mode: {mode}. Use 1 or 2.")

    mgr = get_session_manager()
    sess = mgr.get(session_id)
    if sess is None:
        return _err(f"Session '{session_id}' not found.")

    with sess.lock:
        sess.mode = mode
        mgr.touch(session_id)

    return _ok(session_id=session_id, mode=mode)


def set_step_mode(on: bool, session_id: str) -> dict:
    """Enable or disable step-by-step output mode.

    Args:
        on:          ``True`` to enable, ``False`` to disable.
        session_id:  Session ID.

    Returns:
        ``{"ok": True, "step_mode": bool}`` or error.
    """
    mgr = get_session_manager()
    sess = mgr.get(session_id)
    if sess is None:
        return _err(f"Session '{session_id}' not found.")

    with sess.lock:
        sess.step_mode = on
        mgr.touch(session_id)

    return _ok(session_id=session_id, step_mode=on)


def get_session_info(session_id: str) -> dict:
    """Return metadata about a session (for UI display)."""
    mgr = get_session_manager()
    sess = mgr.get(session_id)
    if sess is None:
        return _err(f"Session '{session_id}' not found.")

    with sess.lock:
        return _ok(
            session_id=sess.session_id,
            mode=sess.mode,
            step_mode=sess.step_mode,
            messages_count=len(sess.messages),
            created_at=sess.created_at,
            last_access=sess.last_access,
        )


def delete_session(session_id: str) -> dict:
    """Delete a session and free its resources."""
    mgr = get_session_manager()
    sess = mgr.get(session_id)
    if sess is None:
        return _err(f"Session '{session_id}' not found.")

    with sess.lock:
        mgr.delete(session_id)

    return _ok(session_id=session_id, message="Session deleted.")
