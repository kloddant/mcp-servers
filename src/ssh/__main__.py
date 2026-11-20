import argparse, asyncio, server
from server import mcp, SessionManager

if __name__ == "__main__":
	parser = argparse.ArgumentParser(description="MCP SSH Read-Only Server")
	parser.add_argument("--config", default="env.json", help="Path to the SSH configuration JSON file")
	args = parser.parse_args()

	# Initialize the global manager in the server module
	server.manager = SessionManager.init(args.config)
	asyncio.run(mcp.run_stdio_async())
