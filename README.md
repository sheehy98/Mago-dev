# Mago Dev Tools

Standalone development tools for ETL operations, schema validation, translation management, and LLM model management.

## Modules

| Module | Purpose |
| ------ | ------- |
| `etl/` | Create, drop, seed, reset, and snapshot database tables and MinIO buckets |
| `schema/` | Validate data catalog CSVs against live database schema |
| `translations/` | Generate and validate frontend translation files |
| `ollama/` | Pull Ollama LLM models |

## Standalone Wrappers

Dev tools use their own database and storage wrappers instead of the API's `lib/`:

- `db.py` — psycopg2 wrapper (`get_connection()`, `execute_query()`)
- `storage.py` — boto3 S3 client factory (`get_s3_client()`)

## Usage

Invoked via the `mago-data` MCP server or `python -m dev.etl.reset_all` from the project root.

## Dependencies

All dependencies are installed via the parent repo's `requirements.txt`.
