# tests/test_memory_fallback.py
# Unit Test Suite for Memory Extractor Gemini Fallback (Phase 6A)

import unittest
from unittest.mock import patch, MagicMock
from memory.memory_manager import should_extract_memory, extract_memory, _call_llm_for_memory


class TestMemoryFallback(unittest.TestCase):
    """Verify actual local-first memory extraction and policy-gated Gemini fallback."""

    @patch("memory.memory_manager.genai", create=True)
    def test_local_success_preferred(self, mock_genai):
        provider = MagicMock()
        provider.chat.return_value = 'YES'
        with patch('core.local_ai_provider.get_local_ai_provider', return_value=provider):
            res = should_extract_memory("My name is Ali", "Nice to meet you Ali")
            self.assertTrue(res)
            provider.chat.assert_called_once()
            mock_genai.Client.assert_not_called()

    @patch("memory.memory_manager._load_gemini_key", return_value="AIzaDummyKey")
    def test_local_unavailable_gemini_fallback(self, mock_gem_key):
        """An unavailable local provider can fall back only when cloud is allowed."""
        mock_response = MagicMock()
        mock_response.text = '{"identity": {"name": {"value": "Ali"}}}'

        mock_g_client = MagicMock()
        mock_g_client.models.generate_content.return_value = mock_response

        provider = MagicMock()
        provider.chat.return_value = None
        with patch('core.local_ai_provider.get_local_ai_provider', return_value=provider), \
             patch('core.ai_policy.is_cloud_ai_allowed', return_value=True), \
             patch('core.ai_policy.assert_cloud_ai_allowed'), \
             patch("google.genai.Client", return_value=mock_g_client):
            res = extract_memory("My name is Ali", "Hello Ali")
            self.assertEqual(res, {"identity": {"name": {"value": "Ali"}}})
            mock_g_client.models.generate_content.assert_called_once()

    def test_both_providers_fail_gracefully(self):
        """Missing providers return an empty result without crashing."""
        provider = MagicMock()
        provider.chat.return_value = None
        with patch('core.local_ai_provider.get_local_ai_provider', return_value=provider), \
             patch("memory.memory_manager._load_gemini_key", return_value=""):
            res = extract_memory("Random text", "Response text")
            self.assertEqual(res, {})

    def test_cloud_policy_blocks_fallback(self):
        provider = MagicMock()
        provider.chat.return_value = None
        with patch('core.local_ai_provider.get_local_ai_provider', return_value=provider), patch('core.ai_policy.is_cloud_ai_allowed', return_value=False), patch('google.genai.Client') as client:
            self.assertEqual(extract_memory('fixture fact','fixture response'), {})
            client.assert_not_called()


if __name__ == "__main__":
    unittest.main()
