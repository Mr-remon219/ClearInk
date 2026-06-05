"""Tests for clearink.tool.skill.core."""

from __future__ import annotations

import unittest

from clearink.tool.skill.core import Skill, get_available_skills, load_skill, _skill


class TestParseFrontmatter(unittest.TestCase):
    """Tests for Skill._parse_frontmatter."""

    def test_valid_yaml_frontmatter(self):
        content = (
            "---\n"
            "name: test_skill\n"
            "description: A test skill\n"
            "---\n"
            "\n"
            "Skill content here."
        )
        result = Skill._parse_frontmatter(content)
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "test_skill")
        self.assertEqual(result["description"], "A test skill")

    def test_missing_closing_returns_none(self):
        content = "---\nname: incomplete\n"
        result = Skill._parse_frontmatter(content)
        self.assertIsNone(result)

    def test_empty_string_returns_none(self):
        result = Skill._parse_frontmatter("")
        self.assertIsNone(result)

    def test_no_frontmatter_returns_none(self):
        content = "Just some regular content without frontmatter."
        result = Skill._parse_frontmatter(content)
        self.assertIsNone(result)


class TestGetAvailableSkills(unittest.TestCase):
    """Tests for get_available_skills."""

    def setUp(self):
        self._original_skills = dict(_skill.AVAILABLE_SKILLS)
        _skill.AVAILABLE_SKILLS.clear()

    def tearDown(self):
        _skill.AVAILABLE_SKILLS.clear()
        _skill.AVAILABLE_SKILLS.update(self._original_skills)

    def test_returns_dict_copy(self):
        _skill.AVAILABLE_SKILLS["skill_a"] = {
            "name": "skill_a",
            "description": "desc a",
        }
        result = get_available_skills()
        self.assertEqual(result, _skill.AVAILABLE_SKILLS)
        self.assertIsNot(result, _skill.AVAILABLE_SKILLS)


class TestLoadSkill(unittest.TestCase):
    """Tests for load_skill."""

    def setUp(self):
        self._original_skills = dict(_skill.AVAILABLE_SKILLS)
        _skill.AVAILABLE_SKILLS.clear()

    def tearDown(self):
        _skill.AVAILABLE_SKILLS.clear()
        _skill.AVAILABLE_SKILLS.update(self._original_skills)

    def test_existing_skill_returns_content_string(self):
        _skill.AVAILABLE_SKILLS["test_skill"] = {
            "name": "test_skill",
            "content": "This is the skill content.",
        }
        result = load_skill("test_skill")
        self.assertEqual(result, "This is the skill content.")

    def test_non_existing_skill_returns_error_containing_bucunzai(self):
        result = load_skill("nonexistent")
        self.assertIn("不存在", result)
