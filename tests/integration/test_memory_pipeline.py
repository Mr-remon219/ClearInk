"""Integration tests for the memory pipeline (store, tool, load).

Tests cover the full lifecycle: writing, reading, listing, consolidating,
overwriting, validating names, rejecting invalid types, parsing frontmatter,
and extracting/normalizing memory candidates from structured text.
"""

from __future__ import annotations


from clearink.system_prompt.memory_store import (
    _parse_frontmatter,
    consolidate_memories,
    is_valid_memory_name,
    list_memory_files,
    read_memory_file,
    write_memory_file,
)
from clearink.system_prompt.memory_tool import save_memory
from clearink.system_prompt.memory_load import (
    _normalize_memory_candidate,
    _parse_extracted_items,
)


# ═══════════════════════════════════════════════════════════════
# 1. Basic write-then-read flow
# ═══════════════════════════════════════════════════════════════

class TestBasicWriteRead:
    """Write a memory file and verify it can be read back and appears in listings."""

    def test_write_then_read_memory(self, tmp_data_dir, monkeypatch):
        # memory_store has its own copy of MEMORY_DIR from import time.
        # Monkeypatch it directly so write/read/list use the temp dir.
        import clearink.system_prompt.memory_store as mstore
        mem_dir = tmp_data_dir / "system_prompts" / ".memory"
        monkeypatch.setattr(mstore, "MEMORY_DIR", mem_dir)

        name = "test-memory"
        description = "A test memory"
        memory_type = "reference"
        content = "This is the content."

        result = write_memory_file(name, description, memory_type, content)
        assert "saved successfully" in result

        raw = read_memory_file(name)
        assert raw is not None
        assert content in raw
        assert name in raw

        entries = list_memory_files()
        matching = [e for e in entries if e["name"] == name]
        assert len(matching) == 1
        assert matching[0]["description"] == description
        assert matching[0]["type"] == memory_type

    def test_write_updates_memory_index(self, tmp_data_dir, monkeypatch):
        import clearink.system_prompt.memory_store as mstore
        mem_dir = tmp_data_dir / "system_prompts" / ".memory"
        monkeypatch.setattr(mstore, "MEMORY_DIR", mem_dir)

        name = "test-memory"
        write_memory_file(name, "A test memory", "reference", "Content.")

        from clearink.config import MEMORY_DIR
        index_path = MEMORY_DIR / "MEMORY.md"
        assert index_path.exists()
        index_text = index_path.read_text(encoding="utf-8")
        assert name in index_text


# ═══════════════════════════════════════════════════════════════
# 2. Batch consolidation
# ═══════════════════════════════════════════════════════════════

class TestConsolidateMemories:
    """consolidate_memories batch writes multiple items at once."""

    def test_consolidate_memories_batch(self, tmp_data_dir, monkeypatch):
        import clearink.system_prompt.memory_store as mstore
        monkeypatch.setattr(mstore, "MEMORY_DIR",
                            tmp_data_dir / "system_prompts" / ".memory")

        items = [
            {
                "name": "memory-one",
                "description": "First memory",
                "type": "reference",
                "content": "Content one.",
            },
            {
                "name": "memory-two",
                "description": "Second memory",
                "type": "knowledge",
                "content": "Content two.",
            },
            {
                "name": "memory-three",
                "description": "Third memory",
                "type": "user",
                "content": "Content three.",
            },
        ]

        result = consolidate_memories(items)
        assert "added:" in result
        assert "memory-one" in result
        assert "memory-two" in result
        assert "memory-three" in result

        entries = list_memory_files()
        names = {e["name"] for e in entries}
        assert "memory-one" in names
        assert "memory-two" in names
        assert "memory-three" in names
        assert len(entries) == 3


# ═══════════════════════════════════════════════════════════════
# 3. Overwriting an existing memory
# ═══════════════════════════════════════════════════════════════

class TestOverwrite:
    """Writing to the same name replaces the existing content."""

    def test_overwrite_same_name(self, tmp_data_dir, monkeypatch):
        import clearink.system_prompt.memory_store as mstore
        monkeypatch.setattr(mstore, "MEMORY_DIR",
                            tmp_data_dir / "system_prompts" / ".memory")

        write_memory_file("dup-test", "First", "reference", "Content 1")
        write_memory_file("dup-test", "Second", "reference", "Content 2")

        raw = read_memory_file("dup-test")
        assert raw is not None
        assert "Content 2" in raw
        assert "Content 1" not in raw

        entries = list_memory_files()
        matching = [e for e in entries if e["name"] == "dup-test"]
        assert len(matching) == 1
        assert matching[0]["description"] == "Second"


# ═══════════════════════════════════════════════════════════════
# 4. Name validation
# ═══════════════════════════════════════════════════════════════

class TestNameValidation:
    """is_valid_memory_name enforces kebab-case slug rules."""

    def test_invalid_name_rejected(self):
        # Uppercase is not allowed
        assert is_valid_memory_name("Invalid-Name") is False
        # Empty string is not allowed
        assert is_valid_memory_name("") is False
        # Starting with a hyphen is not allowed
        assert is_valid_memory_name("-bad") is False
        # Trailing hyphen is allowed? Let's check the regex: ^[a-z0-9][a-z0-9-]{0,127}$
        # Trailing hyphen matches [a-z0-9-] so yes it's allowed, but that's fine
        # What about underscores?
        assert is_valid_memory_name("bad_name") is False
        # Spaces
        assert is_valid_memory_name("bad name") is False

        # Valid names
        assert is_valid_memory_name("valid-name") is True
        assert is_valid_memory_name("a") is True
        assert is_valid_memory_name("abc123") is True
        assert is_valid_memory_name("my-memory-file") is True


# ═══════════════════════════════════════════════════════════════
# 5. save_memory tool handler rejects invalid types
# ═══════════════════════════════════════════════════════════════

class TestSaveMemoryValidation:
    """The registered tool handler validates memory_type before writing."""

    def test_save_memory_rejects_invalid_type(self, tmp_data_dir, monkeypatch):
        import clearink.system_prompt.memory_store as mstore
        monkeypatch.setattr(mstore, "MEMORY_DIR",
                            tmp_data_dir / "system_prompts" / ".memory")
        result = save_memory("good-name", "desc", "invalid_type", "content")
        assert "Invalid memory_type" in result
        assert "invalid_type" in result

    def test_save_memory_rejects_invalid_name(self, tmp_data_dir, monkeypatch):
        import clearink.system_prompt.memory_store as mstore
        monkeypatch.setattr(mstore, "MEMORY_DIR",
                            tmp_data_dir / "system_prompts" / ".memory")
        result = save_memory("Bad-Name", "desc", "reference", "content")
        assert "Invalid memory name" in result

    def test_save_memory_accepts_valid(self, tmp_data_dir, monkeypatch):
        import clearink.system_prompt.memory_store as mstore
        monkeypatch.setattr(mstore, "MEMORY_DIR",
                            tmp_data_dir / "system_prompts" / ".memory")
        result = save_memory("valid-name", "desc", "knowledge", "content")
        assert "saved successfully" in result
        raw = read_memory_file("valid-name")
        assert raw is not None


# ═══════════════════════════════════════════════════════════════
# 6. Empty / nonexistent memory directory
# ═══════════════════════════════════════════════════════════════

class TestEmptyMemoryDir:
    """list_memory_files handles a missing MEMORY_DIR gracefully."""

    def test_empty_memory_dir_handled(self, tmp_data_dir, monkeypatch):
        import clearink.system_prompt.memory_store as mstore

        nonexistent = tmp_data_dir / "nonexistent" / ".memory"
        monkeypatch.setattr(mstore, "MEMORY_DIR", nonexistent)

        assert not nonexistent.exists()
        result = list_memory_files()
        assert result == []


# ═══════════════════════════════════════════════════════════════
# 7. _parse_frontmatter — valid input
# ═══════════════════════════════════════════════════════════════

class TestParseFrontmatterValid:
    """_parse_frontmatter correctly extracts YAML frontmatter."""

    def test_parse_frontmatter_valid(self):
        content = (
            "---\n"
            "name: test-memory\n"
            "description: a test memory\n"
            "type: reference\n"
            "---\n"
            "This is the body."
        )
        meta = _parse_frontmatter(content)
        assert meta is not None
        assert meta.get("name") == "test-memory"
        assert meta.get("description") == "a test memory"
        assert meta.get("type") == "reference"

    def test_parse_frontmatter_no_extra_fields(self):
        content = (
            "---\n"
            "name: minimal\n"
            "---\n"
            "Body."
        )
        meta = _parse_frontmatter(content)
        assert meta is not None
        assert meta.get("name") == "minimal"


# ═══════════════════════════════════════════════════════════════
# 8. _parse_frontmatter — invalid / absent frontmatter
# ═══════════════════════════════════════════════════════════════

class TestParseFrontmatterInvalid:
    """_parse_frontmatter returns None or empty dict for bad input."""

    def test_no_frontmatter(self):
        """No leading '---' means no frontmatter — returns empty metadata dict."""
        meta = _parse_frontmatter("Just plain text without any frontmatter.")
        # frontmatter.loads treats everything as content with no metadata
        assert meta is not None
        assert meta == {}

    def test_unclosed_frontmatter(self):
        """A frontmatter block that isn't closed with '---' returns empty dict.

        The implementation splits on '---' and expects exactly 3 parts.
        With only one delimiter, len(parts) < 3 → returns {}.
        """
        content = "---\nname: open-block\n"
        meta = _parse_frontmatter(content)
        # Implementation returns {} (empty dict) when delimiter count != 2
        assert meta is not None
        assert meta == {}, f"Expected empty dict for unclosed frontmatter, got: {meta}"

    def test_empty_frontmatter(self):
        """--- on its own with nothing between produces empty metadata."""
        content = "---\n---"
        meta = _parse_frontmatter(content)
        assert meta is not None
        assert meta == {}

    def test_malformed_yaml_frontmatter(self):
        """Truly invalid YAML causes _parse_frontmatter to return None."""
        content = "---\n: invalid yaml key\n---\nBody."
        meta = _parse_frontmatter(content)
        assert meta is None


# ═══════════════════════════════════════════════════════════════
# 9. _parse_extracted_items + _normalize_memory_candidate
# ═══════════════════════════════════════════════════════════════

class TestParsedExtractedItemsAndNormalize:
    """_parse_extracted_items parses --- delimited blocks via text."""

    def test_parse_extracted_items_multiple(self):
        text = (
            "---\n"
            "name: memory-alpha\n"
            "description: First extracted memory\n"
            "type: knowledge\n"
            "content: |\n"
            "  Line one of content.\n"
            "  Line two of content.\n"
            "---\n"
            "---\n"
            "name: memory-beta\n"
            "description: Second extracted memory\n"
            "type: reference\n"
            "content: |\n"
            "  Single line.\n"
            "---\n"
        )
        items = _parse_extracted_items(text)
        assert len(items) == 2

        assert items[0]["name"] == "memory-alpha"
        assert items[0]["type"] == "knowledge"
        assert "Line one of content." in items[0]["content"]
        assert "Line two of content." in items[0]["content"]

        assert items[1]["name"] == "memory-beta"
        assert items[1]["type"] == "reference"
        assert "Single line." in items[1]["content"]

    def test_parse_extracted_items_none(self):
        result = _parse_extracted_items("none")
        assert result == []

    def test_parse_extracted_items_empty(self):
        result = _parse_extracted_items("")
        assert result == []

    def test_parse_extracted_items_skip_incomplete(self):
        """Items without 'content' or 'name' should be skipped."""
        text = (
            "---\n"
            "name: only-name\n"
            "description: no content here\n"
            "---\n"
        )
        items = _parse_extracted_items(text)
        assert items == []

    # ── normalize tests ───────────────────────────────────────

    def test_normalize_markdown_list_prefix(self):
        """A leading '- ' should be stripped."""
        result = _normalize_memory_candidate("- my-memory")
        assert result == "my-memory"

    def test_normalize_bracketed_name(self):
        """Names inside square brackets should be extracted."""
        result = _normalize_memory_candidate("[my-memory]")
        assert result == "my-memory"

    def test_normalize_md_suffix(self):
        """Trailing .md should be stripped."""
        result = _normalize_memory_candidate("my-memory.md")
        assert result == "my-memory"

    def test_normalize_valid_kebab_case(self):
        """Plain valid kebab-case names pass through."""
        result = _normalize_memory_candidate("valid-name")
        assert result == "valid-name"

    def test_normalize_invalid_name_returns_empty(self):
        """Invalid names (uppercase, spaces) return empty string."""
        assert _normalize_memory_candidate("Invalid-Name") == ""
        assert _normalize_memory_candidate("") == ""
        assert _normalize_memory_candidate("  ") == ""

    def test_normalize_none_token(self):
        """The literal 'none' returns empty string."""
        assert _normalize_memory_candidate("none") == ""
        assert _normalize_memory_candidate("None") == ""
