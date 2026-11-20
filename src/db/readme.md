# Database MCP Server

A Model Context Protocol (MCP) server that provides a secure, read-only interface for interacting with MariaDB and MySQL databases. This server is designed specifically for LLM consumption, emphasizing state management via handles to protect the LLM's context window from oversized data sets.

## Core Philosophy

### 1. Read-Only by Design
To ensure data integrity and security, this server enforces a strict read-only posture through two layers of defense:

> [!WARNING]
> **Database Permissions**: For maximum security, you should grant **only `SELECT` permissions** and nothing else to the database users used by this server. While the server performs its own privilege verification, relying on the database's own permission system is the most secure approach to prevent unauthorized data modification.

*   **Privilege Verification**: Upon connection, the server checks the database user's grants and raises an error if dangerous privileges (like `FILE`, `SUPER`, `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, or `CREATE`) are detected.
*   **SQL Normalization Pipeline**: Every query is passed through a normalization engine that masks string literals, strips comments, and verifies that the command prefix is within the allowed set (`SELECT`, `SHOW`, `DESC`, `DESCRIBE`, `USE`).

### 2. State Management via Handles
To prevent the LLM from being overwhelmed by large data sets (which can crash the context window), this server uses a **Handle Pattern**:
*   **Connection Handles**: `db__connect` returns a `connection_id`.
*   **Result Handles**: `db__query` returns a `result_id`.
*   **Detailed Retrieval**: The LLM uses `db__dump_result` to fetch specific properties or slices of data (e.g., rows 0-50) using those IDs.

## Configuration

The server requires a JSON configuration file (default: `env.json`) to define connection profiles.

**Example `env.json`:**
```json
{
  "connections": {
    "production_read": {
      "host": "db.example.com",
      "port": 3306,
      "username": "read_user",
      "password": "secure_password"
    },
    "local_dev": {
      "host": "localhost",
      "port": 3306,
      "username": "dev_user",
      "password": "dev_password",
      "database": "app_db"
    }
  }
}
```

## Available Tools

### Connection Management
*   `db__connect`: Establishes a connection using a profile name from the configuration. Returns a `connection_id`.
*   `db__connect_test`: Similar to `db__connect`, but returns the error message as a string instead of raising an exception (useful for debugging connection issues).
*   `db__disconnect`: Closes a specific connection handle or all active connections if no ID is provided.
*   `db__list_connection_names`: Lists available configuration profiles from `env.json`.
*   `db__list_connections`: Lists currently active connection UUIDs.

### Data Retrieval
*   `db__query`: Executes a read-only SQL query. Returns a `result_id`.
*   `db__dump_query`: Retrieves properties of a Query object (e.g., the SQL executed).
*   `db__dump_result`: Retrieves data from a Result object. Supports slicing the `rows` property via `start_row` and `stop_row` to manage context size.
*   `db__list_allowed_commands`: Shows which SQL command prefixes are permitted.

### Introspection
*   `db__inspect_query`: Lists available attributes for a Query handle.
*   `db__inspect_result`: Lists available attributes for a Result handle.
*   `db__get_documentation`: Retrieves this guide.

## Workflow Example

1.  **Connect**: Call `db__list_connection_names()` $\rightarrow$ `db__connect(connection_name="production_read")`.
2.  **Query**: Call `db__query(connection_id="...", sql="SELECT * FROM users LIMIT 100")`.
3.  **Inspect**: Call `db__inspect_result(obj_id="...")` to see available attributes.
4.  **Fetch**: Call `db__dump_result(object_ids=["..."], object_property="rows", start_row=0, stop_row=20)` to get the first 20 rows.

## Technical Implementation
This server is implemented using `pymysql` to provide a pure-Python interface to MariaDB/MySQL, ensuring broad compatibility while maintaining strict control over result buffering and state management.
