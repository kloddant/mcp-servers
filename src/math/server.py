import math, typeguard, uuid
import numpy as np
import pandas as pd
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

mcp = MCPServer("Math")


@mcp.tool()
def math__calculate(func: str, args: list|None = None, kwargs: dict|None = None):
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


@mcp.tool()
async def math__get_documentation() -> str:
	"""
	Purpose: Retrieves the server's documentation, including the state management guide and recommended workflows.
	Produces: The full text of the project readme.
	"""
	try:
		# Resolve the path relative to this script's location
		readme_path = Path(__file__).parent / "readme.md"
		with open(readme_path, "r", encoding="utf-8") as f:
			return f.read()
	except Exception as e:
		return "Documentation currently unavailable: {0}".format(str(e))