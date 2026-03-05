# BAPP Auto API Client — Python

Official Python client for the [BAPP Auto API](https://www.bapp.ro). Provides a
simple, consistent interface for authentication, entity CRUD, and task execution.

## Getting Started

### 1. Install

```bash
pip install bapp-api-client
```

### 2. Create a client

```python
from bapp_api_client import BappApiClient

client = BappApiClient(token="your-api-key")
```

### 3. Make your first request

```python
# List with filters
countries = client.list("core.country", page=1, search="Romania")

# Get by ID
country = client.get("core.country", "42")

# Create
new = client.create("core.country", {"name": "Romania", "code": "RO"})

# Update (full)
client.update("core.country", "42", {"name": "Romania", "code": "RO"})

# Patch (partial)
client.patch("core.country", "42", {"code": "RO"})

# Delete
client.delete("core.country", "42")
```

## Authentication

The client supports **Token** (API key) and **Bearer** (JWT / OAuth) authentication.
Token auth already includes a tenant binding, so you don't need to specify `tenant` separately.

```python
# Static API token (tenant is included in the token)
client = BappApiClient(token="your-api-key")

# Bearer (JWT / OAuth)
client = BappApiClient(bearer="eyJhbG...", tenant="1")
```

## Configuration

`tenant` and `app` can be changed at any time after construction:

```python
client.tenant = "2"
client.app = "wms"
```

## API Reference

### Client options

| Option | Description | Default |
|--------|-------------|---------|
| `token` | Static API token (`Token <value>`) — includes tenant | — |
| `bearer` | Bearer / JWT token | — |
| `host` | API base URL | `https://panel.bapp.ro/api` |
| `tenant` | Tenant ID (`x-tenant-id` header) | `None` |
| `app` | App slug (`x-app-slug` header) | `"account"` |

### Methods

| Method | Description |
|--------|-------------|
| `me()` | Get current user profile |
| `get_app(app_slug)` | Get app configuration by slug |
| `list(content_type, **filters)` | List entities (paginated) |
| `get(content_type, id)` | Get a single entity |
| `create(content_type, data)` | Create an entity |
| `update(content_type, id, data)` | Full update (PUT) |
| `patch(content_type, id, data)` | Partial update (PATCH) |
| `delete(content_type, id)` | Delete an entity |
| `list_introspect(content_type)` | Get list view metadata |
| `detail_introspect(content_type)` | Get detail view metadata |
| `list_tasks()` | List available task codes |
| `detail_task(code)` | Get task configuration |
| `run_task(code, payload?)` | Execute a task |
| `run_task_async(code, payload?)` | Run a long-running task and poll until done |

### Paginated responses

`list()` returns the results directly as a list/array. Pagination metadata is
available as extra attributes:

- `count` — total number of items across all pages
- `next` — URL of the next page (or `null`)
- `previous` — URL of the previous page (or `null`)

## File Uploads

When data contains file objects, the client automatically switches from JSON to
`multipart/form-data`. Mix regular fields and files in the same call:

```python
# File objects, byte strings, or tuples (filename, file) are auto-detected
client.create("myapp.document", {
    "name": "Report",
    "file": open("report.pdf", "rb"),
})

# Tuple form for explicit filename / content-type
client.create("myapp.document", {
    "name": "Report",
    "file": ("report.pdf", open("report.pdf", "rb"), "application/pdf"),
})

# Also works with tasks
client.run_task("myapp.import_data", {
    "format": "csv",
    "file": open("data.csv", "rb"),
})
```

## Tasks

Tasks are server-side actions identified by a dotted code (e.g. `myapp.export_report`).

```python
# List all tasks
tasks = client.list_tasks()

# Inspect a task
cfg = client.detail_task("myapp.export_report")

# Run without payload (GET)
result = client.run_task("myapp.export_report")

# Run with payload (POST)
result = client.run_task("myapp.export_report", {"format": "csv"})
```

### Long-running tasks

Some tasks run asynchronously on the server. When triggered, they return an `id`
that can be polled via `bapp_framework.taskdata`. Use `run_task_async()` to
handle this automatically — it polls until `finished` is `true` and returns the
final task data (which includes a `file` URL when the task produces a download).

## License

MIT
