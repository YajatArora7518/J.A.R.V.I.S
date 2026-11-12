# scripts/test_context_retrieval.py
# Behavior-focused unit and integration tests for Smart Context Retrieval (Phase 4C)

import sys
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.context_retriever import SmartContextRetriever, ContextDomain


class TestSmartContextRetrieval(unittest.TestCase):

    def setUp(self):
        self.retriever = SmartContextRetriever(base_dir=BASE_DIR)

    def test_01_domain_classification(self):
        """Verify accurate domain selection based on request topic."""
        proj_query = "What is causing the python build error in my repository?"
        self.assertEqual(self.retriever.classify_domain(proj_query), ContextDomain.PROJECT)

        college_query = "Aaj meri konsi class hai aur assignment deadline kab hai?"
        self.assertEqual(self.retriever.classify_domain(college_query), ContextDomain.COLLEGE)

        screen_query = "Screen pe kya display ho raha hai, error solve karo"
        self.assertEqual(self.retriever.classify_domain(screen_query), ContextDomain.SCREEN)

        general_query = "How is the weather in Delhi today?"
        self.assertEqual(self.retriever.classify_domain(general_query), ContextDomain.GENERAL)

    def test_02_project_context_bounded_inclusion(self):
        """Verify project question includes project files and code context, not college schedule."""
        ctx = self.retriever.retrieve_context("Check python code in project")
        self.assertEqual(ctx["domain"], ContextDomain.PROJECT.value)
        self.assertIn("project_name", ctx)
        self.assertIn("recent_files", ctx)
        self.assertNotIn("timetable", ctx)  # Timetable must NOT be dumped into project prompts

    def test_03_college_context_bounded_inclusion(self):
        """Verify college query includes timetable and assignments, not project repo internals."""
        ctx = self.retriever.retrieve_context("Meri next class kab hai?")
        self.assertEqual(ctx["domain"], ContextDomain.COLLEGE.value)
        self.assertIn("timetable", ctx)
        self.assertIn("assignments", ctx)
        self.assertNotIn("project_dir", ctx)

    def test_04_general_conversation_context_bounded(self):
        """Verify general conversation includes preferences but does not dump complete DB."""
        ctx = self.retriever.retrieve_context("Hello Jarvis, good morning.")
        self.assertEqual(ctx["domain"], ContextDomain.GENERAL.value)
        self.assertNotIn("timetable", ctx)
        self.assertNotIn("project_dir", ctx)
        # Verify memories are bounded to at most 3 items
        self.assertLessEqual(len(ctx.get("relevant_memories", [])), 3)

    def test_05_secret_credential_redaction(self):
        """Verify sensitive credentials, API keys, and passwords are automatically redacted."""
        sensitive_snippet = "Using API key AIzaSyD98765432101234567890abcdef123456 and sk-abcdef12345678901234567890abcdef"
        redacted = self.retriever._redact_secrets(sensitive_snippet)

        self.assertNotIn("AIzaSyD98765432101234567890abcdef123456", redacted)
        self.assertNotIn("sk-abcdef12345678901234567890abcdef", redacted)
        self.assertIn("[REDACTED_SECRET]", redacted)


if __name__ == "__main__":
    unittest.main()
