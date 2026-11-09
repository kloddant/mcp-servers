# Filesystem MCP Server

A high-performance, stateful filesystem server for the Model Context Protocol (MCP).

## Overview

Unlike standard filesystem servers that return raw data for every request, this filesystem mcp server implements a handle-based architecture. When you read a directory or search for a file, the server creates a virtual object in its memory and returns a **UUID handle**. 

This design is specifically optimized for LLMs to:
1. **Reduce Context Bloat:** Avoid flooding the context window with thousands of lines of text or file lists.
2. **Enable Triage:** Use search results to identify a few specific files before committing to reading their full contents.
3. **Maintain State:** Refer back to previous search results or directory listings using their handles.

## State & Handle Management

Filesystem2 uses a stateful, handle-based system to minimize context window usage. Instead of passing raw file content or directory listings back and forth, the server creates virtual objects in an internal `objects` dictionary and provides the LLM with a UUID handle.

### Handle Lifecycle
*   **Ephemeral Storage:** All handles are stored in volatile server memory. They are not persisted to disk.
*   **Invalidation:** If the server process restarts or crashes, the `objects` dictionary is wiped. All previously issued UUID handles will become invalid, and subsequent calls to `filesystem__serialize` or `filesystem__inspect` using those handles will return an "Object not found" error.
*   **Verification:** Use the `filesystem__list_handles` tool to see a real-time list of all active handles currently held in the server's memory.

### Recommended Discovery Workflow
To navigate the filesystem efficiently and avoid "Object not found" errors, follow this sequence:

1.  **Identify Roots:** Call `filesystem__list_allowed_directories` to determine which areas of the filesystem are accessible.
2.  **Explore:** Use `filesystem__read_directory` or `filesystem__search` to discover files and subdirectories. These tools will populate the server state and return UUID handles.
3.  **Resolve Names (Crucial):** Because `read_directory` returns handles, you must resolve them to filenames. Use `filesystem__serialize` with `object_property='get_manifest'` or `object_property='list_flat'` on a Directory handle to see the mapping of filenames to their respective handles.
4.  **Refine:** Use `filesystem__get_handle_by_name` to resolve specific files within a directory handle you already possess.
5.  **Consume:** Use `filesystem__serialize` to retrieve the actual text content or metadata associated with a handle.
6.  **Inspect:** If you are unsure what properties or methods a handle supports, use `filesystem__inspect`.

### Memory Efficiency
To prevent server instability when dealing with large datasets:
*   **Search Results:** When performing a content search, the server creates only one `File` handle per file, regardless of the number of matches. Use the `line_number` provided in the `SearchResult` to locate specific matches.
*   **Chunked Reading:** When serializing large files, always use the `start_line` and `stop_line` parameters to read the file in manageable chunks rather than attempting to load the entire file into the context window.

## Core Concepts

### The Object Store
The server maintains an internal `objects` dictionary. Every time a tool creates a `Directory`, `File`, or `SearchResult`, it is assigned a unique UUID.

### The Serialization Loop
To get data out of a handle, use the `filesystem__serialize` tool.
- **Default View:** Returns a summary (e.g., file content, directory child handles, or search snippets).
- **Property/Method View:** Pass a specific property or method name (discovered via `filesystem__inspect`) to get a precise value. 
    - *Example:* Use `object_property='get_manifest'` on a Directory handle to get a dictionary of `{filename: handle}`.
    - *Example:* Use `object_property='absolute_path'` to get the full system path of a file.

## Toolset

### Navigation & Reading
- `filesystem__read_directory`: Creates a `Directory` object and returns its handle.
- `filesystem__read_file`: Creates a `File` object and returns its handle.
- `filesystem__serialize`: The primary way to view the contents of any handle. Supports line-range reading for files and calling object methods.

### Search & Discovery
- `filesystem__search`: A powerful query engine that can search by name and/or content. Returns a `SearchResult` handle.
- `filesystem__inspect`: Returns a list of all properties and methods available for a given handle.

## Security

The server implements a strict **Prefix-Based Sandbox**. 
- Only directories explicitly listed in the `--allowed-directories` startup argument (and their subdirectories) can be accessed.
- All paths are resolved to their absolute form to prevent path traversal attacks (e.g., using `..`).
- Access is checked at both the tool entry point and the object instantiation level.

## Installation & Usage

### Requirements
- Python 3.14+
- `mcp` library

### Running the Server
Start the server by passing the allowed root directories:
```bash
python -m filesystem2 --allowed-directories "C:\path\to\allowed\folder" "U:\another\allowed\folder"
