# MCP Servers

This repository is a heavily modified fork of the official [Model Context Protocol (MCP) reference servers](https://github.com/modelcontextprotocol/servers). 

While it started as a clone of the reference implementations, I have expanded it with a suite of custom servers and modified existing ones to better suit my specific workflows.

## 🛠️ Server Index

### Custom Servers (Written by me)
These servers were built from scratch or heavily modified to provide specialized functionality:
*   **Cryptography**: Tools for encryption, decryption, and cryptographic operations.
*   **DB**: Custom database interface and query tools.
*   **Filesystem**: Advanced file system operations.
*   **Geography**: Location-based services and geospatial calculations.
*   **HTML**: Specialized HTML parsing and manipulation tools.
*   **Math**: Extended mathematical functions and calculations.
*   **Regex**: Advanced regular expression testing and manipulation.
*   **SSH**: Remote server management and command execution.

### Reference Servers (Original)
I have retained these official reference implementations for their core utility:
*   **Git**: Tools to read, search, and manipulate Git repositories.
*   **Memory**: Knowledge graph-based persistent memory system.
*   **Sequential Thinking**: Dynamic and reflective problem-solving through thought sequences.
*   **Time**: Time and timezone conversion capabilities.

## 🚀 Local Setup & Running

Since these servers are developed locally, you need to install dependencies and build them before use.

### TypeScript Servers
From the root directory, run:
```sh
npm install
npm run build
```

### Python Servers
For each Python server, set up a local virtual environment:
```sh
cd src/<server-name>
python -m venv venv
.\venv\Scripts\activate
pip install .
```

## ⚙️ Client Configuration

To use these servers in Jan, you must configure them individually. Point the configuration directly to the local build files and the specific executables.

*(Note: Ensure the paths to `node.exe` and `python.exe` match your local installation)*

**Example Node Server:**
```json
{
  "CustomDB": {
    "command": "C:\\Program Files\\nodejs\\node.exe",
    "args": ["C:\\path\\to\\modelcontextprotocol\\src\\db\\build\\index.js"],
    "env": {},
    "type": "stdio",
    "active": true
  }
}
```

**Example Python Server:**
```json
{
  "Git": {
    "command": "C:\\path\\to\\modelcontextprotocol\\src\\git\\venv\\Scripts\\python.exe",
    "args": ["-m", "mcp_server_git"],
    "env": {},
    "type": "stdio",
    "active": true
  }
}
```
