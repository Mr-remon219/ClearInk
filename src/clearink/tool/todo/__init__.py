"""Flat TODO list — simple status tracking without dependency support."""

from .core import todo_write, get_todos, CURRENT_TODOS

__all__ = ["todo_write", "get_todos", "CURRENT_TODOS"]
