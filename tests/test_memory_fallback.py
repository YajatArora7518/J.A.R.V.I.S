# tests/test_memory_fallback.py
# Unit Test Suite for Memory Extractor Gemini Fallback (Phase 6A)

import unittest
from unittest.mock import patch, MagicMock
from memory.memory_manager import should_extract_memory, extract_memory, _call_llm_for_memory


class TestMemoryFallback(unittest.TestCase):
    """Verify OpenRouter -> Gemini -> Graceful Failure fallback chain."""

    @patch("memory.memory_manager.genai", create=True)
    def test_openrouter_success_preferred(self, mock_genai):
        """When OpenRouter is available, it should be used first."""
        with patch("or_client.client.chat", return_value="YES") as mock_or_chat, \
             patch("or_client._load_api_key", return_value="sk-or-dummy"):
            res = should_extract_memory("My name is Ali", "Nice to meet you Ali")
            self.assertTrue(res)
            mock_or_chat.assert_called_once()
            mock_genai.Client.assert_not_called()

    @patch("memory.memory_manager._load_gemini_key", return_value="AIzaDummyKey")
    def test_openrouter_fails_gemini_fallback(self, mock_gem_key):
        """When OpenRouter fails or is unconfigured, Gemini API should be used as fallback."""
        mock_response = MagicMock()
        mock_response.text = '{"identity": {"name": {"value": "Ali"}}}'

        mock_g_client = MagicMock()
        mock_g_client.models.generate_content.return_value = mock_response

        with patch("or_client._load_api_key", side_effect=RuntimeError("Key missing")), \
             patch("google.genai.Client", return_value=mock_g_client):
            res = extract_memory("My name is Ali", "Hello Ali")
            self.assertEqual(res, {"identity": {"name": {"value": "Ali"}}})
            mock_g_client.models.generate_content.assert_called_once()

    def test_both_providers_fail_gracefully(self):
        """When both OpenRouter and Gemini API fail, it should return empty result without crashing."""
        with patch("or_client._load_api_key", side_effect=RuntimeError("No OR key")), \
             patch("memory.memory_manager._load_gemini_key", return_value=""):
            res = extract_memory("Random text", "Response text")
            self.assertEqual(res, {})


if __name__ == "__main__":
    unittest.main()
