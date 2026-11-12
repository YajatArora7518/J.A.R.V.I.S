"""Bind a tool's arguments before invoking it, so failures never replay actions."""
import inspect


def invoke_tool(function, parameters, player=None, **extras):
    try:
        signature = inspect.signature(function)
    except (ValueError, TypeError):
        return function(parameters)
    names = signature.parameters
    variadic = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in names.values())
    optional = {"player": player, **extras}
    if not variadic:
        optional = {k: v for k, v in optional.items() if k in names}
    if "parameters" in names or variadic:
        arguments = {"parameters": parameters, **optional}
        signature.bind(**arguments)
        return function(**arguments)
    positional = [p for p in names.values() if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)]
    if positional and positional[0].name in ("params", "args", "p", "arguments"):
        signature.bind(parameters, **optional)
        return function(parameters, **optional)
    arguments = {k: v for k, v in parameters.items() if k in names}
    arguments.update(optional)
    signature.bind(**arguments)
    return function(**arguments)
