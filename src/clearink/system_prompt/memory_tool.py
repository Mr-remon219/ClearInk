from ..tool.register import register_tool
from .memory_store import write_memory_file

_VALID_TYPES = {"user", "feedback", "project", "reference", "knowledge"}


@register_tool(
    name="save_memory",
    description=(
        "Save a piece of information to persistent memory. "
        "Use this when you learn something worth remembering across sessions: "
        "user preferences, research interests, feedback on recommendations, "
        "verified formula-to-paper dependencies, frequently referenced papers, "
        "or project context. Memory files are stored with YAML frontmatter and "
        "the MEMORY.md index is automatically updated."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Short kebab-case slug for the memory file (e.g. 'user-research-focus', 'formula-attention-is-all-you-need')",
            },
            "description": {
                "type": "string",
                "description": "One-line summary used to decide relevance in future conversations",
            },
            "memory_type": {
                "type": "string",
                "description": "Memory type: user (user profile/preferences), feedback (corrections/confirmations), project (research project context), reference (external resource pointers), or knowledge (literature dependency chains)",
            },
            "content": {
                "type": "string",
                "description": "The full memory content — specific, actionable, and self-contained",
            },
        },
        "required": ["name", "description", "memory_type", "content"],
    },
)
def save_memory(name: str, description: str, memory_type: str, content: str) -> str:
    if memory_type not in _VALID_TYPES:
        return (
            f"Invalid memory_type: {memory_type!r}. "
            f"Must be one of {sorted(_VALID_TYPES)}. Memory not saved."
        )
    return write_memory_file(name, description, memory_type, content)
