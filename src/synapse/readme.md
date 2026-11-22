# Synapse MCP Server

Synapse is a Model Context Protocol (MCP) bridge that allows a primary LLM to offload specific tasks to one or more secondary LLM nodes across your network.

This is designed to prevent the main LLM's context window from being cluttered with "Chain of Thought" noise or raw data processing by delegating tasks to other available hardware (nodes), effectively creating a distributed inference network.

## Architecture
`Main LLM` $\rightarrow$ `Synapse MCP` $\rightarrow$ `llama.cpp API (Node)` $\rightarrow$ `Main LLM`

## Installation
1. Ensure you have `llama.cpp` (server mode) running as a service on your target nodes.
2. Install the required Python dependencies:
   ```bash
   pip install .
   ```

## Configuration
Synapse uses an `env.json` file to map Node IDs to their respective API endpoints. This allows you to route tasks to different physical machines based on their capabilities.

### `env.json` Structure
Create a file named `env.json` with the following format:

```json
{
  "agents": {
    "self": {
      "endpoint": "http://127.0.0.1:<port>/v1"
    },
    "laptop": {
      "endpoint": "http://<agent-ip>:<port>/v1"
    },
    "old_desktop": {
      "endpoint": "http://<agent-ip>:<port>/v1"
    }
  }
}
```

## Integration with Jan
To add Synapse to Jan, use the following configuration in the MCP settings:

**Command:**
`python <path-to-synapse>\__main__.py --config <path-to-synapse>\env.json`

## Tools

### `synapse__ask`
The primary tool used by the LLM to offload work to a specific node.

**Arguments:**
- `prompt` (string): The specific task or question to be handled by the node.
- `agent_id` (string, optional): The ID of the node to use (e.g., `'self'`, `'laptop'`, `'old_desktop'`). 
           Defaults to `"self"`.

**Example Usage:**
If the main LLM needs to process a large file and knows the `old_desktop` has the most VRAM, it will call:
`synapse__ask(prompt="Analyze this large dataset...", agent_id="old_desktop")`

### `synapse__list_agents`
Lists all available agents currently configured in the synapse network, including their model, provider, and endpoint.

**Arguments:**
- None

### `synapse__get_documentation`
Retrieves the full text of the Synapse README to provide the LLM with updated instructions on how to use the network.

## Best Practices for System Prompts
To get the most out of Synapse, add the following to your main LLM's system instructions:

> "You have access to a distributed network of LLM nodes via the `synapse__ask` tool. To preserve your own context window and optimize performance, offload heavy lifting to the appropriate node:
> - **Self**: Use for quick, low-latency sub-tasks.
> - **Old Desktop**: Use for large-context tasks, deep analysis, or heavy data processing.
> - **Laptop**: Use for secondary verification or parallel processing.
> 
> Only incorporate the final result of the node's work into your main conversation to keep your context window clean."
