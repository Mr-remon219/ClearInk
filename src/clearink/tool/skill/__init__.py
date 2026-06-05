"""Skill loader — scans data/skills/ for SKILL.md files and makes them invocable."""

from .core import Skill, get_available_skills, load_skill

__all__ = ["Skill", "get_available_skills", "load_skill"]
