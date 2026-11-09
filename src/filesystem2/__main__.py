import argparse, asyncio, server
from server import mcp

if __name__ == "__main__":
	parser = argparse.ArgumentParser(description="MCP Filesystem Server")
	parser.add_argument(
		"--allowed-directories",
		nargs="*",
		required=True,
		help="List of directories that the llm is allowed to read.",
	)
	args = parser.parse_args()

	server.allowed_directories.update(args.allowed_directories)

	asyncio.run(mcp.run_stdio_async())
