"""Background task execution — automatic dispatch of slow operations."""

from .core import (  # noqa: F401
    background_tasks,
    background_results,
    background_lock,
    strip_runtime_control_args,
    is_slow_operation,
    should_run_background,
    start_background_task,
    collect_background_results,
)
from .tools import get_background_result, list_background_tasks  # noqa: F401
