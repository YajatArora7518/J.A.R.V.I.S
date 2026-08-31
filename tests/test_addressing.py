# tests/test_addressing.py
# Dedicated Automated Test Suite for User Addressing ("Boss" / "Sir") Safety & Intent Invariance

import unittest
import sys
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.intent_router import classify_intent
from actions.open_app import open_app
from actions.whatsapp import whatsapp
from actions.telegram import telegram
from actions.college_mode import college_mode


class TestUserAddressingSafetyAndInvariance(unittest.TestCase):

    FORBIDDEN_COMBINATIONS = [
        "boss sir",
        "sir boss",
        "yes boss sir",
        "yes sir boss",
        "ji boss sir",
        "ji sir boss",
        "done boss sir",
        "done sir boss"
    ]

    def _assert_no_forbidden_addressing(self, response_text: str):
        """Verifies that no response contains both Boss AND Sir in the same output."""
        if not response_text:
            return

        lower_text = response_text.lower()

        # Check explicit forbidden strings
        for bad in self.FORBIDDEN_COMBINATIONS:
            self.assertNotIn(bad, lower_text, f"Forbidden addressing combination '{bad}' found in: {response_text!r}")

        # Check simultaneous occurrence of both 'boss' and 'sir'
        has_boss = bool(re.search(r"\bboss\b", lower_text))
        has_sir  = bool(re.search(r"\bsir\b", lower_text))
        self.assertFalse(
            has_boss and has_sir,
            f"Response contains both 'Boss' and 'Sir' simultaneously: {response_text!r}"
        )

    # 1. RESPONSE STRING ADDRESSING VALIDATION
    def test_sample_valid_and_invalid_addressing(self):
        valid_responses = [
            "Yes Boss, Chrome khol raha hoon.",
            "Yes Sir, check kar raha hoon.",
            "Done, Boss.",
            "Done, Sir.",
            "Ji Boss.",
            "Ji Sir.",
            "Checking that, Boss.",
            "Opening WhatsApp, Sir."
        ]
        for v in valid_responses:
            self._assert_no_forbidden_addressing(v)

        invalid_responses = [
            "Yes Boss Sir, Chrome khol raha hoon.",
            "Yes Sir Boss, check kar raha hoon.",
            "Done, Boss Sir.",
            "Done, Sir Boss."
        ]
        for inv in invalid_responses:
            with self.assertRaises(AssertionError):
                self._assert_no_forbidden_addressing(inv)

    # 2. TOOL RESPONSE OUTPUT ADDRESSING SAFETY
    def test_open_app_response_addressing(self):
        res1 = open_app(parameters={"app_name": "notepad"})
        self._assert_no_forbidden_addressing(res1)

    def test_whatsapp_response_addressing(self):
        res = whatsapp(action="open")
        self._assert_no_forbidden_addressing(res.get("message", ""))

    def test_telegram_response_addressing(self):
        res = telegram(action="open")
        self._assert_no_forbidden_addressing(res.get("message", ""))

    def test_college_mode_response_addressing(self):
        res = college_mode(parameters={"action": "schedule"})
        self._assert_no_forbidden_addressing(res.get("message", ""))

    # 3. INTENT CLASSIFICATION INVARIANCE UNDER ADDRESSING
    def test_intent_routing_invariance(self):
        # WhatsApp Message
        r1 = classify_intent("Rahul ko WhatsApp message bhej")
        self.assertEqual(r1["intent"], "WHATSAPP_MESSAGE")

        # WhatsApp Call
        r2 = classify_intent("Rahul ko WhatsApp call karo")
        self.assertEqual(r2["intent"], "WHATSAPP_CALL")

        # WhatsApp Read
        r3 = classify_intent("Rahul ka WhatsApp message batao")
        self.assertEqual(r3["intent"], "WHATSAPP_READ")

        # College Query
        r4 = classify_intent("Today meri class kya hai")
        self.assertEqual(r4["intent"], "COLLEGE_QUERY")

        # Web Search
        r5 = classify_intent("Google pe search karo AI news")
        self.assertEqual(r5["intent"], "WEB_SEARCH")

    def test_intent_routing_prefix_invariance(self):
        """Verifies that adding 'Boss' or 'Sir' to a user command yields the exact same intent."""
        plain = classify_intent("Chrome kholo")
        boss  = classify_intent("Boss Chrome kholo")
        sir   = classify_intent("Sir Chrome kholo")
        self.assertEqual(plain["intent"], boss["intent"])
        self.assertEqual(plain["intent"], sir["intent"])

        msg_plain = classify_intent("Rahul ko WhatsApp message bhej")
        msg_boss  = classify_intent("Boss Rahul ko WhatsApp message bhej")
        msg_sir   = classify_intent("Sir Rahul ko WhatsApp message bhej")
        self.assertEqual(msg_plain["intent"], msg_boss["intent"])
        self.assertEqual(msg_plain["intent"], msg_sir["intent"])
        self.assertEqual(msg_boss["intent"], "WHATSAPP_MESSAGE")

        sched_plain = classify_intent("Today meri class kya hai")
        sched_boss  = classify_intent("Boss Today meri class kya hai")
        sched_sir   = classify_intent("Sir Today meri class kya hai")
        self.assertEqual(sched_plain["intent"], sched_boss["intent"])
        self.assertEqual(sched_plain["intent"], sched_sir["intent"])


if __name__ == "__main__":
    unittest.main()
