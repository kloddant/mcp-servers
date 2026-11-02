import math, typeguard, uuid
import numpy as np
import pandas as pd
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

mcp = MCPServer("Math")


@mcp.tool()
def math_calculate(func: str, args: list|None = None, kwargs: dict|None = None):
	"""
		Purpose: Perform a mathematical calculation using the Python math module.
		Parameters:
			func: The name of the math function (e.g., 'sqrt', 'sin', 'log').
			args: A list of arguments to pass to the function.
			kwargs: A dict of keyword arguments to pass to the function.
	"""

	args = args or []
	kwargs = kwargs or {}

	if not func:
		raise ToolError("Please provide a function name.")

	if not hasattr(math, func):
		raise ToolError(f"Function {func} not found in math module.")
	
	attr = getattr(math, func)
	
	if callable(attr):
		try:
			return attr(*args, **kwargs)
		except Exception as e:
			raise ToolError(f"Error calculating {func}: {str(e)}")
	else:
		return attr