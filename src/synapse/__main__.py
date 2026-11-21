# __main__.py
import argparse, server, asyncio

if __name__ == "__main__":
	parser = argparse.ArgumentParser(description="MCP Synapse Server")
	parser.add_argument("--config", default="env.json", help="Path to config")
	args = parser.parse_args()
	
	# Load config directly from the server module
	server.load_config(args.config)
	
	asyncio.run(server.mcp.run_stdio_async())
