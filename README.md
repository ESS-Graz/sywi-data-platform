# SYWI Data Platform

A data platform built with [Dagster](https://dagster.io/) and [LanceDB](https://lancedb.com/). Assets are stored as Lance tables, which you can query with [DuckDB](https://duckdb.org/) 2.0.

> **Only want to query the Ikariam data?** See [Getting Started with the Data](ikariam/README.md#getting-started-with-the-data).

## Prerequisites

### Required

| Tool | macOS | Windows | Linux |
|------|-------|---------|-------|
| [uv](https://github.com/astral-sh/uv) | `brew install uv` | `winget install --id=astral-sh.uv -e` | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| [just](https://github.com/casey/just) | `brew install just` | `winget install --id=Casey.Just --exact` | `brew install just` or [see docs](https://just.systems/man/en/packages.html) |
| [Docker](https://docs.docker.com/get-docker/) (only to run pipelines) | Docker Desktop | Docker Desktop | `apt install docker.io docker-compose` |

Production Docker builds use Docker Hardened Images from `dhi.io`. Log in before
building or deploying:

```bash
docker login dhi.io
```

### Optional

| Tool | macOS | Windows | Linux |
|------|-------|---------|-------|
| [DuckDB CLI](https://duckdb.org/docs/installation/) | `brew install duckdb` | `winget install DuckDB.cli` | [See docs](https://duckdb.org/docs/installation/) |

DuckDB CLI (version 2.0 or newer, for the core `lance` extension) is only needed for the `just db` command (interactive SQL session).

## Quick Start

```bash
# 1. Clone and enter the project
git clone https://github.com/ESS-Graz/sywi-data-platform.git
cd sywi-data-platform

# 2. Create your local environment file
cp .env.example .env.local
# Or place the .env.local you received via email in the root folder

# 3. Start the development environment
just up

# 4. Open http://localhost:3000 in your browser
```

## Concepts

This platform uses Dagster for orchestration. Here's how our terminology maps to Dagster:

| Term | Dagster Concept | Description |
|------|-----------------|-------------|
| **Project** | Code Location | A folder with `pyproject.toml` and its own virtual environment. Each project is deployed as a separate Dagster code location with isolated dependencies. |
| **Asset** | Asset | A logical unit of data (e.g., a table, dataset, or file). Defined with the `@asset` decorator. |
| **Asset Group** | Asset Group | A way to organize assets visually in the Dagster UI using the `group_name` parameter. |

A single project can contain multiple asset groups.

## Local Development

### What `just up` Does

1. **Syncs enabled projects** - Creates/updates virtual environments
2. **Starts PostgreSQL** - Runs in Docker (Dagster stores its run history and metadata there)
3. **Runs Dagster** - Starts the dev server via `dg dev`

Each project runs in its own isolated Python environment, allowing different dependency versions without conflicts.

### Hot Reload

The dev environment automatically detects code changes:

1. Edit files in any project's `src/` directory
2. Dagster detects the change automatically
3. Click **"Reload"** in the Dagster UI to apply changes

### Configuration

The `.env.local` file configures your local environment:

```bash
# Local Lance database: one directory, one table per asset
LANCE_URI=./data/lance
```

Each asset is stored as a LanceDB table named after the asset, for example `./data/lance/hackernews_stories.lance`. Writing an asset replaces the whole table. `LANCE_URI` can also be an S3 path (`s3://bucket/path`), in which case the `AWS_*` credentials from `.env.example` are used.

Dagster stores its run history and metadata in PostgreSQL (`dagster_db` database).

### Running Specific Projects

By default, `just up` starts all projects defined in `dg.toml`. To start only specific projects, set `DEV_PROJECTS` in `.env.local`:

```bash
# Start only the hackernews project
DEV_PROJECTS=hackernews

# Start multiple projects (comma-separated)
DEV_PROJECTS=hackernews,ikariam

# Start all projects (default if empty or not set)
# DEV_PROJECTS=
```

This is useful when working on a single project and wanting faster startup times.

### Working with Data

#### Raw Input Files

Raw files that feed pipelines should live under `data/raw/<project>/` instead of
inside project packages. The `data/` directory is mounted into Docker services as
read-only raw input storage and is ignored by Git, except for small,
hand-maintained lookup tables that `.gitignore` re-includes by name (currently
`data/raw/ikariam/building_costs.csv`).

For example, Ikariam expects:

```text
data/raw/ikariam/<lowercase-server>/<snapshot_date>/<table>.parquet
```

The platform root and raw-data location are inferred; no environment variable
is required.

#### Interactive DuckDB Session

```bash
just db
```

Opens a DuckDB shell (the DuckDB CLI, version 2.0 or newer, must be installed) with your local Lance database attached as `local` and the remote one as `remote`:

```sql
-- Show local tables
SHOW TABLES FROM local;

-- Query local data
SELECT * FROM local.hackernews_stories LIMIT 10;

-- Query remote data (if LANCE_REMOTE_URI is set; with several remotes use their names)
SELECT * FROM remote.hackernews_stories LIMIT 10;
SELECT * FROM hackernews.hackernews_stories LIMIT 10;
```

Use `just db -l` to skip connecting to remote. `just db -f <file.sql>` runs one SQL file in such a session and exits; the path is relative to the repository root, for example `just db -f ikariam/sql/explore/01_coverage.sql`.

#### Pull Data from Remote

If you have access to remote Lance databases, configure them in `.env.local`. A single URI is attached as `remote`. For several, give each a name (`name=uri`, comma separated); each is attached under its name:

```bash
LANCE_REMOTE_URI=ikariam=s3://ikariam/ikariam.lancedb,hackernews=s3://hackernews/lance
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_ENDPOINT_URL=https://data.systems-sciences.uni-graz.at
AWS_REGION=us-east-1
```

Then pull tables:

```bash
# List available remote tables
just pull

# Pull a complete table
just pull hackernews_stories

# Pull only 1000 rows (faster iteration)
just pull hackernews_stories 1000

# With several remotes the list shows <remote>.<table>. A table that exists in
# only one remote is found automatically; otherwise choose with --from
just pull player_snapshot 1000 --from ikariam
```

Pulling a table of more than 5 million rows without a row limit is refused, so you do not copy
a huge table by accident (`patents.google_patents` has 116 million rows). Give a limit, or
confirm with `--yes`.

Pulled tables are automatically marked as materialized in Dagster.

#### Export Data

```bash
# Export as Parquet (default)
just export customers

# Export as CSV
just export customers csv

# Export a remote table (name of the remote: `remote`, or its name from LANCE_REMOTE_URI)
just export customers parquet remote
just export hackernews_stories csv hackernews
```

Supported formats: `parquet`, `csv`, `json`, `ndjson`

## Adding a New Project

```bash
just new my_project
```

This creates a new project (Dagster code location) and registers it in `dg.toml`:

```
my_project/
├── pyproject.toml
├── Dockerfile
└── src/my_project/
    ├── __init__.py
    ├── definitions.py
    └── assets/
        └── __init__.py
```

Then:

1. Add assets in `my_project/src/my_project/assets/`
2. Export them in `assets/__init__.py`
3. Register them in `definitions.py`
4. Add dependencies to `pyproject.toml`
5. Run `just up` - the new project loads automatically

### Example Asset

```python
# my_project/src/my_project/assets/example.py
import pandas as pd
from dagster import asset

@asset(group_name="my_data_ingestion")
def my_asset() -> pd.DataFrame:
    return pd.DataFrame({"col": [1, 2, 3]})
```

## Cross-Project Dependencies

Projects can depend on assets from other projects using the Lance database as the data contract. The table name is the asset name:

```python
import lancedb
from dagster import SourceAsset, asset
from sywi_core import lance_config_from_env

# Declare external dependency
hackernews_stories = SourceAsset(
    key="hackernews_stories",
    description="Stories from hackernews project",
)

@asset(deps=[hackernews_stories])
def my_analysis():
    config = lance_config_from_env()
    db = lancedb.connect(config["uri"], storage_options=config.get("storage_options"))
    df = db.open_table("hackernews_stories").to_pandas()
    # ... your analysis
    return result
```

## Client Libraries

For accessing the SYWI Lance databases from external scripts or notebooks:

### Python: sywi-duckdb

```bash
pip install git+https://github.com/ESS-Graz/sywi-data-platform.git#subdirectory=libs/sywi_duckdb
```

```python
import sywi_duckdb as duckdb

conn = duckdb.connect()
conn.execute("SELECT * FROM local.my_table").fetchdf()
```

### R: sywi.duckdb

```r
remotes::install_github("ESS-Graz/sywi-data-platform", subdir = "libs/sywi.duckdb")
```

```r
library(sywi.duckdb)
con <- dbConnect(sywi_duckdb())
dbGetQuery(con, "SELECT * FROM local.my_table")
```

## Command Reference

| Command | Description |
|---------|-------------|
| `just up` | Start development environment |
| `just down` | Stop PostgreSQL |
| `just new <name>` | Create a new project (Dagster code location) |
| `just db` | Open interactive DuckDB session |
| `just db -l` | DuckDB session (local only, skip remote) |
| `just db -f <file.sql>` | Run one SQL file in a DuckDB session and exit |
| `just pull` | List remote tables |
| `just pull <table>` | Pull table from remote |
| `just pull <table> <limit>` | Pull limited rows |
| `just pull ... --from <name>` | Pull from a specific remote (when there are several) |
| `just export <table> [format] [source]` | Export table to file |
| `just logs [service]` | View Docker logs |
| `just prod` | Start production-like environment |
| `just generate` | Generate production Docker Compose |
| `just clean` | Remove local Dagster state |

## Troubleshooting

### `just up` fails with "No such file or directory: .venv/bin/python"

The subproject virtual environments need to be created. This should happen automatically, but you can manually sync:

```bash
cd hackernews && uv sync && cd ..
cd ikariam && uv sync && cd ..
```

### `just db` fails with "Failed to download extension lance (HTTP 404)"

The `lance` extension is a core extension from DuckDB 2.0. Check `duckdb --version` and upgrade the DuckDB CLI if it is older than 2.0.

### Docker permission errors on Linux

Add your user to the docker group:

```bash
sudo usermod -aG docker $USER
# Then log out and back in
```

---

## Production Deployment

Production runs on Docker with each project as a separate container communicating via gRPC.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Server                               │
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │  PostgreSQL │  │  SeaweedFS  │  │   Dagster Webserver │ │
│  │  (Dagster)  │  │  (S3 data)  │  │     (port 3000)     │ │
│  │             │  │             │  │                     │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
│         │                │                    │             │
│  ┌──────┴────────────────┴────────────────────┴──────────┐ │
│  │              Pipeline Containers (gRPC)               │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌────────────┐  │ │
│  │  │  hackernews  │  │   ikariam    │  │    ...     │  │ │
│  │  │  (port 4000) │  │  (port 4000) │  │            │  │ │
│  │  └──────────────┘  └──────────────┘  └────────────┘  │ │
│  └───────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### Configuration

Production `.env` file:

```bash
LANCE_URI=s3://bucket/path
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_ENDPOINT_URL=https://data.systems-sciences.uni-graz.at
AWS_REGION=us-east-1
```

### Deployment Scripts

#### Generate Configuration

```bash
just generate
```

Scans for projects and generates:

- `docker-compose.prod.yaml` - All services
- `workspace.yaml` - Dagster workspace config

#### Manual Deploy

```bash
./deploy.sh
```

Pulls latest code, builds images, and restarts containers.

#### Auto-Deploy (Watchdog)

```bash
./watchdog.sh
```

Polls GitHub every 60 seconds and auto-deploys on changes.

### Docker Images

Production images are based on Docker Hardened Images. Each project has its own
`Dockerfile` that:

1. Uses a DHI Python `-dev` build stage with `uv` copied from the DHI uv image
2. Installs the project package into `/opt/dagster/venv`
3. Copies the virtual environment into a non-dev DHI Python runtime image
4. Runs the Dagster gRPC server on port 4000

The `Dockerfile.dagster` image runs the webserver and daemon.
