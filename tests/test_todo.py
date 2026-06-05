"""Tests for clearink.tool.todo.core."""

import unittest
import clearink.tool.todo.core as todo_core


class TestTodoWrite(unittest.TestCase):
    """todo_write handles merge and replace semantics."""

    def setUp(self):
        # Use module-level access because todo_core.todo_write(merge=False) reassigns
        # the todo_core.CURRENT_TODOS global, breaking direct-from imports.
        todo_core.CURRENT_TODOS.clear()

    def test_merge_adds_new_items(self):
        todo_core.todo_write([{"id": "1", "content": "Item one"}], merge=True)
        self.assertEqual(len(todo_core.CURRENT_TODOS), 1)
        self.assertEqual(todo_core.CURRENT_TODOS[0]["content"], "Item one")

    def test_merge_updates_existing_by_id(self):
        todo_core.todo_write([{"id": "1", "content": "Original"}], merge=True)
        todo_core.todo_write([{"id": "1", "content": "Updated"}], merge=True)
        self.assertEqual(len(todo_core.CURRENT_TODOS), 1)
        self.assertEqual(todo_core.CURRENT_TODOS[0]["content"], "Updated")

    def test_merge_updates_status(self):
        todo_core.todo_write([{"id": "1", "content": "Task", "status": "pending"}], merge=True)
        todo_core.todo_write([{"id": "1", "content": "Task", "status": "completed"}], merge=True)
        self.assertEqual(todo_core.CURRENT_TODOS[0]["status"], "completed")

    def test_merge_preserves_other_fields(self):
        todo_core.todo_write([{"id": "1", "content": "Task", "status": "pending"}], merge=True)
        todo_core.todo_write([{"id": "1", "status": "completed"}], merge=True)
        self.assertEqual(todo_core.CURRENT_TODOS[0]["content"], "Task")
        self.assertEqual(todo_core.CURRENT_TODOS[0]["status"], "completed")

    def test_merge_adds_multiple_new_items(self):
        todo_core.todo_write([
            {"id": "1", "content": "First"},
            {"id": "2", "content": "Second"},
        ], merge=True)
        self.assertEqual(len(todo_core.CURRENT_TODOS), 2)

    def test_replace_clears_existing(self):
        todo_core.todo_write([{"id": "1", "content": "Old"}], merge=True)
        todo_core.todo_write([{"id": "2", "content": "New"}], merge=False)
        self.assertEqual(len(todo_core.CURRENT_TODOS), 1)
        self.assertEqual(todo_core.CURRENT_TODOS[0]["id"], "2")

    def test_replace_empty_list(self):
        todo_core.todo_write([{"id": "1", "content": "Item"}], merge=True)
        todo_core.todo_write([], merge=False)
        self.assertEqual(len(todo_core.CURRENT_TODOS), 0)

    def test_merge_new_item_without_id_field(self):
        todo_core.todo_write([{"content": "No id"}], merge=True)
        self.assertEqual(len(todo_core.CURRENT_TODOS), 1)
        self.assertIsNone(todo_core.CURRENT_TODOS[0].get("id"))

    def test_returns_formatted_string(self):
        result = todo_core.todo_write([{"id": "1", "content": "My task"}], merge=True)
        self.assertIsInstance(result, str)
        self.assertIn("My task", result)


class TestGetTodos(unittest.TestCase):
    """get_todos returns copies of the internal list."""

    def setUp(self):
        todo_core.CURRENT_TODOS.clear()

    def test_returns_empty_list_initially(self):
        self.assertEqual(todo_core.get_todos(), [])

    def test_returns_same_items(self):
        todo_core.todo_write([{"id": "1", "content": "Task A"}], merge=True)
        todos = todo_core.get_todos()
        self.assertEqual(len(todos), 1)
        self.assertEqual(todos[0]["content"], "Task A")

    def test_modifying_returned_list_does_not_affect_internal_state(self):
        todo_core.todo_write([{"id": "1", "content": "Protected"}], merge=True)
        external = todo_core.get_todos()
        external.append({"id": "2", "content": "Hack"})
        self.assertEqual(len(todo_core.CURRENT_TODOS), 1)

    def test_modifying_returned_dict_does_not_affect_internal_state(self):
        todo_core.todo_write([{"id": "1", "content": "Protected"}], merge=True)
        external = todo_core.get_todos()
        external[0]["content"] = "Hacked"
        self.assertEqual(todo_core.CURRENT_TODOS[0]["content"], "Protected")

    def test_multiple_calls_return_independent_copies(self):
        todo_core.todo_write([{"id": "1", "content": "Stable"}], merge=True)
        a = todo_core.get_todos()
        b = todo_core.get_todos()
        a[0]["content"] = "Changed"
        self.assertEqual(b[0]["content"], "Stable")


class TestFormatTodos(unittest.TestCase):
    """_format_todos produces a human-readable todo list."""

    def setUp(self):
        todo_core.CURRENT_TODOS.clear()

    def test_empty_list_returns_no_todos(self):
        self.assertEqual(todo_core._format_todos(), "(no todos)")

    def test_shows_status_icons(self):
        todo_core.todo_write([
            {"id": "1", "content": "Pending task", "status": "pending"},
            {"id": "2", "content": "In progress", "status": "in_progress"},
            {"id": "3", "content": "Completed", "status": "completed"},
        ], merge=True)
        output = todo_core._format_todos()
        self.assertIn("[ ]", output)
        self.assertIn("[~]", output)
        self.assertIn("[x]", output)

    def test_shows_content(self):
        todo_core.todo_write([{"id": "1", "content": "Buy milk"}], merge=True)
        output = todo_core._format_todos()
        self.assertIn("Buy milk", output)

    def test_shows_index_numbers(self):
        todo_core.todo_write([
            {"id": "a", "content": "First"},
            {"id": "b", "content": "Second"},
        ], merge=True)
        output = todo_core._format_todos()
        self.assertIn("#1", output)
        self.assertIn("#2", output)

    def test_default_status_is_pending(self):
        todo_core.todo_write([{"id": "1", "content": "No status"}], merge=True)
        output = todo_core._format_todos()
        self.assertIn("[ ]", output)
