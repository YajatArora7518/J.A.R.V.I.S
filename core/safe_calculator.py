# core/safe_calculator.py
# Constrained AST-Based Safe Mathematical Evaluator for JARVIS
# Strictly evaluates basic arithmetic and mathematical expressions without unsafe eval()/exec().

import ast
import math
import re
from typing import Dict, Any, Union

SAFE_MATH_FUNCS = {
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "log": math.log,
    "log10": math.log10,
    "log2": math.log2,
    "exp": math.exp,
    "ceil": math.ceil,
    "floor": math.floor,
    "factorial": math.factorial,
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "pow": pow,
}

SAFE_MATH_CONSTS = {
    "pi": math.pi,
    "e": math.e,
    "tau": math.tau,
}


def _safe_eval_node(node: ast.AST) -> Union[int, float]:
    """Recursively evaluates AST nodes using strictly whitelisted operations."""
    if isinstance(node, ast.Expression):
        return _safe_eval_node(node.body)

    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError(f"Unsupported constant type: {type(node.value).__name__}")

    if isinstance(node, ast.BinOp):
        left = _safe_eval_node(node.left)
        right = _safe_eval_node(node.right)

        if isinstance(node.op, ast.Add):
            return left + right
        elif isinstance(node.op, ast.Sub):
            return left - right
        elif isinstance(node.op, ast.Mult):
            return left * right
        elif isinstance(node.op, ast.Div):
            if right == 0:
                raise ZeroDivisionError("Division by zero")
            return left / right
        elif isinstance(node.op, ast.FloorDiv):
            if right == 0:
                raise ZeroDivisionError("Division by zero")
            return left // right
        elif isinstance(node.op, ast.Mod):
            if right == 0:
                raise ZeroDivisionError("Modulo by zero")
            return left % right
        elif isinstance(node.op, ast.Pow):
            if isinstance(right, (int, float)) and right > 10000:
                raise ValueError("Exponent too large for safe evaluation")
            return left ** right
        else:
            raise ValueError(f"Unsupported binary operator: {type(node.op).__name__}")

    if isinstance(node, ast.UnaryOp):
        operand = _safe_eval_node(node.operand)
        if isinstance(node.op, ast.UAdd):
            return +operand
        elif isinstance(node.op, ast.USub):
            return -operand
        else:
            raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")

    if isinstance(node, ast.Call):
        func_name = ""
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == "math":
            func_name = node.func.attr
        else:
            raise ValueError("Unsupported function invocation")

        if func_name in SAFE_MATH_FUNCS:
            args = [_safe_eval_node(arg) for arg in node.args]
            return SAFE_MATH_FUNCS[func_name](*args)
        raise ValueError(f"Function '{func_name}' is not permitted in safe calculator")

    if isinstance(node, ast.Name):
        if node.id in SAFE_MATH_CONSTS:
            return SAFE_MATH_CONSTS[node.id]
        raise ValueError(f"Undefined identifier: {node.id}")

    raise ValueError(f"Unsupported syntax construct: {type(node).__name__}")


def normalize_math_query(text: str) -> str:
    """
    Normalizes natural language conversational queries into valid mathematical syntax.
    Examples:
      - 'Calculate 25 times 37' -> '25 * 37'
      - 'What is 984 divided by 12?' -> '984 / 12'
      - 'Calculate 2^10' -> '2 ** 10'
      - 'What is the square root of 144?' -> 'sqrt(144)'
      - 'Compute 17 percent of 850' -> '(17 / 100) * 850'
      - 'What\'s 125 + 378?' -> '125 + 378'
    """
    raw = (text or "").strip()
    s = raw.lower()

    # Normalize wake words & prefixes
    s = re.sub(r"^(boss|sir|jarvis|hey jarvis|ok jarvis)[,\s]+", "", s).strip()
    s = re.sub(r"^(what\s+is|what\'s|whats|calculate|compute|solve|find|evaluate|tell\s+me)(\s+(the|value\s+of|result\s+of))?\s+", "", s).strip()
    s = re.sub(r"^(the\s+)?", "", s).strip()
    s = re.sub(r"[?!.,;]+$", "", s).strip()

    # Square root / cube root
    s = re.sub(r"\bsquare\s+root\s+of\s+([0-9.]+)", r"sqrt(\1)", s)
    s = re.sub(r"\bsqrt\s+of\s+([0-9.]+)", r"sqrt(\1)", s)
    s = re.sub(r"\bcube\s+root\s+of\s+([0-9.]+)", r"(\1 ** (1/3))", s)

    # Percentage expressions: '17 percent of 850' or '17% of 850'
    s = re.sub(r"([0-9.]+)\s*(?:percent|%)\s+of\s+([0-9.]+)", r"(\1 / 100) * \2", s)

    # Powers & exponents: '2^10', '2 raised to 10', '2 to the power of 10'
    s = re.sub(r"([0-9.]+)\s*(?:raised\s+to(?:\s+the)?\s+power\s+of|\^|to\s+the\s+power\s+of|raised\s+to|power)\s*([0-9.]+)", r"\1 ** \2", s)

    # Word arithmetic substitutions
    s = re.sub(r"\b(times|multiplied\s+by|multiplied\s+with|into|cross)\b", "*", s)
    s = re.sub(r"\b(divided\s+by|divided\s+with|over)\b", "/", s)
    s = re.sub(r"\b(plus|added\s+to)\b", "+", s)
    s = re.sub(r"\b(minus|subtracted\s+by|less)\b", "-", s)
    s = re.sub(r"\b(mod|modulo)\b", "%", s)

    return s.strip()


def calculate(query: str) -> Dict[str, Any]:
    """
    Safely calculates mathematical results from expressions or natural language queries.
    Returns structured result dict.
    """
    clean_expr = normalize_math_query(query)
    if not clean_expr:
        return {
            "success": False,
            "error": "Empty mathematical expression.",
            "message": "No mathematical expression provided to calculate."
        }

    try:
        parsed = ast.parse(clean_expr, mode="eval")
        raw_result = _safe_eval_node(parsed)

        # Format integer values cleanly without .0
        if isinstance(raw_result, float) and raw_result.is_integer():
            final_result = int(raw_result)
        elif isinstance(raw_result, float):
            final_result = round(raw_result, 6)
        else:
            final_result = raw_result

        return {
            "success": True,
            "result": final_result,
            "formatted_result": str(final_result),
            "expression": clean_expr,
            "query": query,
            "message": f"The answer is {final_result}."
        }
    except ZeroDivisionError:
        return {
            "success": False,
            "error": "Division by zero",
            "message": "Cannot divide by zero, sir."
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Could not evaluate calculation: {e}"
        }
