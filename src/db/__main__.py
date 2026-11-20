# __main__.py
import argparse, server, asyncio, state

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MCP Database Read-Only Server")
    parser.add_argument("--config", default="env.json", help="Path to config")
    args = parser.parse_args()
    
    # The state module handles the loading internally
    state.load_config(args.config)
    
    asyncio.run(server.mcp.run_stdio_async())
