import argparse, asyncio, server
from server import mcp

if __name__ == "__main__":
	parser = argparse.ArgumentParser(description="MCP Fetch Server")
	parser.add_argument(
		"--allowed-hosts",
		nargs="*",
		required=True,
		help="List of allowed hostnames to fetch from (e.g. google.com github.com)",
	)
	parser.add_argument(
		"--http-request-headers",
		nargs="*",
		help="Global headers in Key:Value format (e.g. Authorization:Bearer token)",
	)
	args = parser.parse_args()

	server.allowed_hosts.update(args.allowed_hosts)

	if args.http_request_headers:
		for header in args.http_request_headers:
			if ":" in header:
				key, value = header.split(":", 1)
				server.CLI_HEADERS[key.strip()] = value.strip()

	asyncio.run(mcp.run_stdio_async())
