# sywi-duckdb

DuckDB wrapper with auto-configured SYWI Lance connections.

## Installation

```bash
pip install git+https://github.com/ESS-Graz/sywi-data-platform.git#subdirectory=libs/sywi_duckdb

# Or with uv
uv add git+https://github.com/ESS-Graz/sywi-data-platform.git#subdirectory=libs/sywi_duckdb
```

Requires DuckDB 2.0 or newer: the `lance` extension is a core extension there.

## Usage

```python
import sywi_duckdb as duckdb

# connect() auto-loads .env / .env.local and attaches local + remote
conn = duckdb.connect()

# Query local database
df = conn.execute("SELECT * FROM local.customers LIMIT 10").fetchdf()

# Query remote database
df = conn.execute("SELECT * FROM remote.customers LIMIT 10").fetchdf()

# Copy a remote table to your local database
conn.execute("COPY (SELECT * FROM remote.customers) TO './data/lance/customers.lance' (FORMAT lance, mode 'overwrite')")

# All standard duckdb functions still work
duckdb.query("SELECT 1 + 1")
```

## Configuration

Create a `.env.local` file in your project root (or any parent directory):

```bash
# Local Lance database (a directory, default ./data/lance)
LANCE_URI=./data/lance

# Remote Lance database (optional). One URI is attached as `remote`; several are
# comma separated name=uri pairs, attached under their names:
LANCE_REMOTE_URI=ikariam=s3://ikariam/ikariam.lancedb,hackernews=s3://hackernews/lance

# S3 credentials, needed when a URI starts with s3://
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_ENDPOINT_URL=https://data.systems-sciences.uni-graz.at
AWS_REGION=us-east-1
```

## Databases

| Database | Description |
|----------|-------------|
| `local`  | Your local Lance database |
| `remote` | The remote Lance database (a single URI in `LANCE_REMOTE_URI`) |
| `<name>` | With several remotes, each one under its own name, for example `ikariam.player_snapshot` |

Prefix table names with the database name: `local.my_table`, `remote.my_table`.
