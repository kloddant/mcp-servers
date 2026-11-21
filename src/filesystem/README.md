# Filesystem MCP Server (v2)

A high-performance, path-centric filesystem server for the Model Context Protocol (MCP) designed specifically to optimize LLM context window usage and navigation.

## Overview

This server provides a suite of tools that allow LLMs to interact with the filesystem using a familiar, shell-like interface. Unlike previous versions, this version is **path-centric**, meaning it uses absolute and relative paths to reduce cognitive load and tool-call overhead.

The server maintains a stateful **Current Working Directory (CWD)** and implements strict output controls to prevent "context bloat" (flooding the LLM's window with too much data).

## Command Reference

| Tool | Linux Equivalent | Description | Key Parameters |
| :--- | :--- | :--- | :--- |
| `filesystem__ls` | `ls` | Lists filenames and directory names in the current or specified path. | `path` (opt), `start_index`, `stop_index` (default 100) |
| `filesystem__tree` | `tree` | Returns a structured JSON hierarchy of the directory tree. | `path` (opt), `max_depth`, `folders_only` |
| `filesystem__cat` | `cat` | Reads content from one or multiple files. | `path` (str or list), `start_line`, `stop_line` (default 100) |
| `filesystem__grep` | `grep` | Searches file contents via regex. | `pattern`, `path` (opt), `max_depth` |
| `filesystem__find` | `find` | Searches for files/dirs by name via regex. | `pattern`, `path` (opt), `max_depth` |
| `filesystem__glob` | `glob` | Finds files/dirs using glob patterns (e.g., `**/*.py`). | `pattern`, `path` (opt) |
| `filesystem__stat` | `stat` | Retrieves comprehensive file/directory metadata. | `path` |
| `filesystem__pwd` | `pwd` | Returns the current working directory. | N/A |
| `filesystem__cd` | `cd` | Changes the current working directory. | `path` |

## Key LLM Workflows

### 1. Project Discovery (The "Zoom" Method)
To understand a new project without wasting tokens:
1.  **High-Level Map:** Use `filesystem__tree(max_depth=2, folders_only=True)` to see the folder architecture.
2.  **Targeted List:** Use `filesystem__ls(path="src/controllers")` to see the files in a specific area of interest.
3.  **File Triage:** Use `filesystem__grep` or `filesystem__glob` to find specific logic or file types.
4.  **Deep Read:** Use `filesystem__cat` to read the relevant files.

### 2. Context Window Management
To prevent hitting token limits, the server implements:
*   **Paginated Listing (`ls`):** Returns a subset of entries. If the total count exceeds the `stop_index`, the LLM should request the next page.
*   **Chunked Reading (`cat`):** Defaults to the first 100 lines. The output explicitly states the **Total Lines in File**, allowing the LLM to request subsequent chunks (e.g., `start_line=100, stop_line=200`).
*   **Structural Filtering (`tree`):** The `folders_only` flag allows the LLM to map a project's structure without listing thousands of individual files.

## Security

The server implements a strict **Prefix-Based Sandbox**:
*   **Allowed Roots:** Only directories explicitly listed in the server configuration (and their subdirectories) are accessible.
*   **Path Normalization:** All paths are resolved to their absolute form using `Path.resolve()` to prevent path traversal attacks (e.g., `..` escapes).
*   **Verification:** Every tool call re-verifies that the resolved path resides within an allowed root.

## Configuration Example

When adding this server to your MCP configuration, ensure you provide the absolute paths to the directories you wish to make accessible:

```json
{
  "Filesystem2": {
    "command": "path/to/python.exe",
    "args": [
      "path/to/__main__.py",
      "--allowed-directories",
      "C:\\Users\\USER\\Documents\\ProjectA",
      "D:\\Projects\\ProjectB"
    ],
    "type": "stdio"
  }
}
```
