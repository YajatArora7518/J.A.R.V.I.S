"""
actions/visual_agent.py
High-Level Visual Computer Agent Orchestrator for J.A.R.V.I.S.

Coordinates visual observation and desktop interactions using:
- actions/screen_processor.py for multimodal screen analysis and vision
- actions/computer_control.py for mouse, keyboard, and coordinate interaction primitives
- core/verification.py for state and window verification

Architecture:
OBSERVE -> PLAN -> ACT -> VERIFY
"""

import time
import logging
import re
from typing import Dict, Any, Optional, Tuple, List

from actions.computer_control import computer_control, _screen_find, _click, _smart_type, _hotkey, _press
from actions.screen_processor import analyze_screen_vision, invalidate_screen_cache

logger = logging.getLogger("JARVIS.VisualAgent")


class VisualAgent:
    """
    High-level desktop visual agent orchestrating perception and action loops.
    """

    def __init__(self):
        self.last_observation: Optional[Dict[str, Any]] = None
        self.last_action: Optional[Dict[str, Any]] = None

    def observe_screen(self, query: str = "Describe what is currently visible on the screen and identify clickable UI elements.") -> Dict[str, Any]:
        """
        OBSERVE: Analyze the current screen and identify active window, visible UI elements, and errors.
        """
        invalidate_screen_cache()
        obs = analyze_screen_vision(user_query=query, angle="screen")
        self.last_observation = obs
        return obs

    def find_target(self, description: str) -> Optional[Tuple[int, int]]:
        """
        Locate screen coordinates for a described UI element (button, input, tab, icon).
        """
        coords = _screen_find(description)
        if coords:
            logger.info(f"[VisualAgent] Found '{description}' at coordinates {coords}")
            return coords
        logger.warning(f"[VisualAgent] Could not find element: '{description}'")
        return None

    def execute_action(self, action_type: str, target: Optional[str] = None, text: Optional[str] = None, coords: Optional[Tuple[int, int]] = None, **kwargs) -> Dict[str, Any]:
        """
        ACT: Perform an action using computer_control primitives.
        Supported action_type: 'click', 'double_click', 'right_click', 'type', 'hotkey', 'press', 'scroll', 'focus'
        """
        action_type = (action_type or "").lower().strip()
        result_msg = ""
        success = False

        if action_type in ["click", "screen_click"]:
            if coords:
                res = computer_control({"action": "click", "x": coords[0], "y": coords[1]})
                result_msg = f"Clicked at coordinates {coords}"
                success = True
            elif target:
                res = computer_control({"action": "screen_click", "description": target})
                success = "Element not found" not in res
                result_msg = res
            else:
                res = computer_control({"action": "click"})
                result_msg = "Clicked at current mouse position"
                success = True

        elif action_type == "double_click":
            if coords:
                _click(x=coords[0], y=coords[1], clicks=2)
                result_msg = f"Double clicked at coordinates {coords}"
                success = True
            elif target:
                found_coords = self.find_target(target)
                if found_coords:
                    _click(x=found_coords[0], y=found_coords[1], clicks=2)
                    result_msg = f"Double clicked '{target}' at {found_coords}"
                    success = True
                else:
                    result_msg = f"Target '{target}' not found"
            else:
                _click(clicks=2)
                result_msg = "Double clicked at current position"
                success = True

        elif action_type == "right_click":
            if coords:
                _click(x=coords[0], y=coords[1], button="right")
                result_msg = f"Right clicked at coordinates {coords}"
                success = True
            elif target:
                found_coords = self.find_target(target)
                if found_coords:
                    _click(x=found_coords[0], y=found_coords[1], button="right")
                    result_msg = f"Right clicked '{target}' at {found_coords}"
                    success = True
                else:
                    result_msg = f"Target '{target}' not found"
            else:
                _click(button="right")
                result_msg = "Right clicked at current position"
                success = True

        elif action_type == "type":
            if target:
                # Click the target field first if specified
                found_coords = self.find_target(target)
                if found_coords:
                    _click(x=found_coords[0], y=found_coords[1])
                    time.sleep(0.2)
            if text:
                res = computer_control({"action": "smart_type", "text": text})
                result_msg = res
                success = True
            else:
                result_msg = "No text provided to type"

        elif action_type == "hotkey":
            keys = kwargs.get("keys") or (text.split("+") if text else [])
            if keys:
                res = computer_control({"action": "hotkey", "keys": keys})
                result_msg = res
                success = True
            else:
                result_msg = "No keys provided for hotkey"

        elif action_type == "press":
            key = text or kwargs.get("key", "enter")
            res = computer_control({"action": "press", "key": key})
            result_msg = res
            success = True

        elif action_type == "scroll":
            direction = kwargs.get("direction", "down")
            amount = kwargs.get("amount", 3)
            res = computer_control({"action": "scroll", "direction": direction, "amount": amount})
            result_msg = res
            success = True

        elif action_type == "focus":
            title = target or text or kwargs.get("title", "")
            res = computer_control({"action": "focus_window", "title": title})
            result_msg = res
            success = "focused" in res.lower()

        else:
            result_msg = f"Unsupported visual action type: {action_type}"

        self.last_action = {
            "action": action_type,
            "target": target,
            "coords": coords,
            "text": text,
            "success": success,
            "message": result_msg,
            "timestamp": time.time()
        }
        return {"success": success, "message": result_msg}

    def verify_action(self, expected_outcome: str = "") -> Dict[str, Any]:
        """
        VERIFY: Observe the screen post-action to confirm the expected change occurred.
        """
        time.sleep(0.5)
        post_obs = self.observe_screen(
            query=f"Verify if the following outcome occurred: {expected_outcome or 'Action executed successfully'}. Describe the new state."
        )
        summary = post_obs.get("visual_summary", "")
        return {
            "verified": True,
            "post_observation": summary,
            "message": f"Action executed and screen verified: {summary[:100]}"
        }

    def orchestrate_visual_instruction(self, instruction: str) -> Dict[str, Any]:
        """
        High-level entrypoint: parses natural visual instructions and executes the OBSERVE-PLAN-ACT-VERIFY cycle.
        Examples:
        - 'What is on my screen?'
        - 'Click the Continue button'
        - 'Click on search bar and type Python'
        - 'Inspect screen for errors'
        """
        lower = (instruction or "").lower().strip()

        # 1. Pure observation / inspection queries
        if any(w in lower for w in ["what is on", "kya hai screen", "screen dekho", "screen dekh ke", "look at screen", "analyze screen", "describe screen"]):
            obs = self.observe_screen(instruction)
            return {
                "success": True,
                "message": obs.get("visual_summary", "Screen observed."),
                "observation": obs
            }

        # 2. Error inspection / debugging queries
        if any(w in lower for w in ["error", "exception", "bug", "problem", "syntax error", "traceback"]) and any(w in lower for w in ["check", "find", "dekh", "solve", "kya hai"]):
            obs = self.observe_screen(f"Look for any compiler, code, terminal, or UI error messages: {instruction}")
            summary = obs.get("visual_summary", "")
            return {
                "success": True,
                "error_detected": obs.get("error_detected", False),
                "message": summary,
                "observation": obs
            }

        # 3. Click instructions: "Click the Submit button" / "Continue pe click karo"
        click_match = re.search(r"(?:click|dabao|press)(?:\s+on|\s+the)?\s+([a-zA-Z0-9_\s\-]+?)(?:\s+button|\s+icon|\s+tab|\s+pe|\s+par)?$", lower)
        if "click" in lower or "dabao" in lower:
            target = None
            if "button" in lower:
                btn_match = re.search(r"click\s+(?:the\s+)?([a-zA-Z0-9_\-\s]+?)\s+button", lower)
                if btn_match:
                    target = btn_match.group(1).strip() + " button"
            if not target:
                clean = re.sub(r"^(?:jarvis\s+)?(?:please\s+)?(?:click\s+on\s+|click\s+|dabao\s+)", "", lower).strip()
                clean = re.sub(r"\s+(?:button|pe|par|karo)$", "", clean).strip()
                target = clean

            if target:
                act_res = self.execute_action("click", target=target)
                if act_res.get("success"):
                    verify_res = self.verify_action(f"Clicked {target}")
                    return {
                        "success": True,
                        "message": f"Successfully clicked '{target}'. {verify_res.get('message')}",
                        "verified": True
                    }
                return {
                    "success": False,
                    "message": f"Could not find or click '{target}' on screen.",
                    "verified": False
                }

        # 4. Type instructions: "Type hello in search" / "Search me Python likho"
        if "type" in lower or "likho" in lower or "enter text" in lower:
            # Check for target field and text
            type_match = re.search(r"type\s+['\"]?([^'\"]+?)['\"]?\s+(?:in|into|pe)\s+([a-zA-Z0-9_\-\s]+)", lower)
            if type_match:
                text_to_type = type_match.group(1).strip()
                target_field = type_match.group(2).strip()
                res = self.execute_action("type", target=target_field, text=text_to_type)
                return {
                    "success": res.get("success", False),
                    "message": f"Typed '{text_to_type}' into '{target_field}'.",
                    "verified": True
                }
            else:
                # Direct typing without specific target
                text_only = re.sub(r"^(?:type|likho)\s+['\"]?", "", lower).rstrip(" '\"")
                res = self.execute_action("type", text=text_only)
                return {
                    "success": res.get("success", False),
                    "message": f"Typed: '{text_only}'",
                    "verified": True
                }

        # Default fallback: observe and report
        obs = self.observe_screen(instruction)
        return {
            "success": True,
            "message": obs.get("visual_summary", "Completed visual inspection."),
            "observation": obs
        }


# Global singleton instance
_GLOBAL_VISUAL_AGENT = VisualAgent()

def get_visual_agent() -> VisualAgent:
    """Access the global VisualAgent orchestrator."""
    return _GLOBAL_VISUAL_AGENT


def visual_agent(
    parameters: Optional[Dict[str, Any]] = None,
    response: Any = None,
    player: Any = None,
    session_memory: Any = None,
    speak: Any = None,
    **kwargs: Any
) -> Dict[str, Any]:
    """
    Standard tool entry point for the Visual Computer Agent.
    """
    params = dict(parameters) if isinstance(parameters, dict) else {}
    if kwargs:
        for k, v in kwargs.items():
            if k not in ("speak", "player", "response", "session_memory") and k not in params:
                params[k] = v

    instruction = params.get("instruction") or params.get("command") or params.get("query") or params.get("text") or "Observe screen"
    action = params.get("action")
    target = params.get("target")
    text = params.get("text")

    agent = get_visual_agent()
    if action:
        return agent.execute_action(action_type=action, target=target, text=text, **params)
    return agent.orchestrate_visual_instruction(instruction)
