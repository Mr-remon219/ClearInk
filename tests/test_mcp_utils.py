from __future__ import annotations

import unittest

from clearink.tool.mcp_client.utils import (
    normalize_mcp_name,
    _mcp_tool_name,
    _parse_mcp_tool_name,
    _convert_json_schema_to_anthropic,
)


class TestNormalizeMcpName(unittest.TestCase):
    """Test normalize_mcp_name for various input patterns."""

    def test_spaces_to_underscores(self) -> None:
        self.assertEqual(normalize_mcp_name("My Server"), "my_server")

    def test_hyphens_to_underscores(self) -> None:
        self.assertEqual(normalize_mcp_name("brave-search"), "brave_search")

    def test_empty_string_returns_empty(self) -> None:
        self.assertEqual(normalize_mcp_name(""), "")

    def test_only_special_chars_returns_empty(self) -> None:
        self.assertEqual(normalize_mcp_name("!!!"), "")

    def test_upper_becomes_lower(self) -> None:
        self.assertEqual(normalize_mcp_name("UPPER"), "upper")

    def test_leading_trailing_underscores_stripped(self) -> None:
        self.assertEqual(normalize_mcp_name("__x__"), "x")

    def test_multiple_underscores_collapsed(self) -> None:
        self.assertEqual(normalize_mcp_name("a___b"), "a_b")

    def test_already_normalized_unchanged(self) -> None:
        self.assertEqual(normalize_mcp_name("a_b"), "a_b")

    def test_mixed_case_and_special_chars(self) -> None:
        self.assertEqual(normalize_mcp_name("My-Cool_Server!!"), "my_cool_server")

    def test_digits_preserved(self) -> None:
        self.assertEqual(normalize_mcp_name("server2"), "server2")

    def test_leading_digits_preserved(self) -> None:
        self.assertEqual(normalize_mcp_name("2fast"), "2fast")


class TestMcpToolName(unittest.TestCase):
    """Test _mcp_tool_name construction."""

    def test_basic_name(self) -> None:
        self.assertEqual(_mcp_tool_name("srv", "tool"), "mcp__srv__tool")

    def test_name_with_underscores(self) -> None:
        self.assertEqual(
            _mcp_tool_name("my_server", "my_tool"),
            "mcp__my_server__my_tool",
        )


class TestParseMcpToolName(unittest.TestCase):
    """Test _parse_mcp_tool_name parsing."""

    def test_valid_name(self) -> None:
        self.assertEqual(_parse_mcp_tool_name("mcp__srv__tool"), ("srv", "tool"))

    def test_not_mcp_prefix_returns_none(self) -> None:
        self.assertIsNone(_parse_mcp_tool_name("not_mcp"))

    def test_empty_string_returns_none(self) -> None:
        self.assertIsNone(_parse_mcp_tool_name(""))

    def test_prefix_only_returns_none(self) -> None:
        self.assertIsNone(_parse_mcp_tool_name("mcp__"))

    def test_prefix_only_no_separator_returns_none(self) -> None:
        self.assertIsNone(_parse_mcp_tool_name("mcp__srv"))

    def test_name_with_underscores(self) -> None:
        self.assertEqual(
            _parse_mcp_tool_name("mcp__my_server__my_tool"),
            ("my_server", "my_tool"),
        )


class TestConvertJsonSchemaToAnthropic(unittest.TestCase):
    """Test _convert_json_schema_to_anthropic schema conversion."""

    def test_empty_properties(self) -> None:
        schema = _convert_json_schema_to_anthropic({})
        self.assertEqual(schema, {"type": "object", "properties": {}})

    def test_empty_properties_explicit(self) -> None:
        schema = _convert_json_schema_to_anthropic({"properties": {}})
        self.assertEqual(schema, {"type": "object", "properties": {}})

    def test_with_properties(self) -> None:
        prop_schema = {
            "properties": {
                "name": {"type": "string", "description": "The name"},
                "age": {"type": "integer", "description": "The age"},
            }
        }
        schema = _convert_json_schema_to_anthropic(prop_schema)
        self.assertEqual(schema["type"], "object")
        self.assertIn("name", schema["properties"])
        self.assertEqual(schema["properties"]["name"]["type"], "string")
        self.assertEqual(
            schema["properties"]["name"]["description"], "The name"
        )
        self.assertIn("age", schema["properties"])
        self.assertEqual(schema["properties"]["age"]["type"], "integer")
        self.assertEqual(schema["properties"]["age"]["description"], "The age")
        # No required field since none was specified
        self.assertNotIn("required", schema)

    def test_with_required_list(self) -> None:
        prop_schema = {
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
            },
            "required": ["name"],
        }
        schema = _convert_json_schema_to_anthropic(prop_schema)
        self.assertEqual(schema["required"], ["name"])

    def test_with_enum(self) -> None:
        prop_schema = {
            "properties": {
                "color": {
                    "type": "string",
                    "description": "Pick a color",
                    "enum": ["red", "green", "blue"],
                }
            }
        }
        schema = _convert_json_schema_to_anthropic(prop_schema)
        self.assertEqual(
            schema["properties"]["color"]["enum"], ["red", "green", "blue"]
        )

    def test_non_dict_property_skipped(self) -> None:
        prop_schema = {
            "properties": {
                "valid": {"type": "string"},
                "invalid": "not_a_dict",
            }
        }
        schema = _convert_json_schema_to_anthropic(prop_schema)
        self.assertIn("valid", schema["properties"])
        self.assertNotIn("invalid", schema["properties"])

    def test_non_string_required_skipped(self) -> None:
        prop_schema = {
            "properties": {"x": {"type": "string"}},
            "required": ["x", 42, None],
        }
        schema = _convert_json_schema_to_anthropic(prop_schema)
        self.assertEqual(schema.get("required"), ["x"])

    def test_property_without_type(self) -> None:
        prop_schema = {
            "properties": {
                "desc": {"description": "Just a description, no type"}
            }
        }
        schema = _convert_json_schema_to_anthropic(prop_schema)
        self.assertNotIn("type", schema["properties"]["desc"])


if __name__ == "__main__":
    unittest.main()
