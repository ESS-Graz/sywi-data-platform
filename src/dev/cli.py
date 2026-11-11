#!/usr/bin/env python3
"""Cross-platform development CLI for Dagster projects.

Usage:
    uv run dev <command> [options]
    just <command>
"""

import os
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import duckdb
import typer
from dotenv import load_dotenv
from rich.console import Console

# Setup paths and load environment
SCRIPT_DIR = Path(__file__).parent.parent.parent.resolve()
ENV_FILE = SCRIPT_DIR / ".env.local"
PROD_COMPOSE = "docker-compose.prod.yaml"

# Load .env.local if it exists
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)

# Rich console for pretty output
console = Console()
err_console = Console(stderr=True)

# Typer app
app = typer.Typer(
    help="Local development CLI for Dagster projects.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


def run(
    cmd: list[str],
    check: bool = True,
    capture_output: bool = False,
    cwd: Optional[Path] = None,
) -> subprocess.CompletedProcess:
    """Run a subprocess command."""
    return subprocess.run(
        cmd,
        check=check,
        capture_output=capture_output,
        text=True,
        cwd=cwd or SCRIPT_DIR,
    )


def run_foreground(cmd: list[str], cwd: Optional[Path] = None) -> int:
    """Run a command in foreground with proper cross-platform signal handling.

    This replaces os.execvp() which doesn't work correctly on Windows.
    Properly forwards Ctrl+C and handles cleanup.
    """
    # On Windows, we need special handling for console processes
    kwargs: dict = {"cwd": cwd or SCRIPT_DIR}

    if sys.platform == "win32":
        # CREATE_NEW_PROCESS_GROUP allows the child to receive Ctrl+C
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

    proc = subprocess.Popen(cmd, **kwargs)

    def signal_handler(sig: int, frame) -> None:
        """Forward signal to child process and exit."""
        if proc.poll() is None:  # Process still running
            if sys.platform == "win32":
                # On Windows, send CTRL_BREAK_EVENT to the process group
                proc.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                proc.terminate()

        proc.wait()
        sys.exit(128 + sig)

    # Set up signal handlers
    original_sigint = signal.signal(signal.SIGINT, signal_handler)
    original_sigterm = signal.signal(signal.SIGTERM, signal_handler)

    try:
        return proc.wait()
    finally:
        # Restore original handlers
        signal.signal(signal.SIGINT, original_sigint)
        signal.signal(signal.SIGTERM, original_sigterm)

        # Ensure process is terminated
        if proc.poll() is None:
            proc.terminate()
            proc.wait()


def docker_compose(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    """Run a docker compose command."""
    return run(["docker", "compose", *args], check=check)


def docker_compose_prod(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    """Run a docker compose command with production compose file."""
    return run(["docker", "compose", "-f", PROD_COMPOSE, *args], check=check)


def require_env(name: str) -> str:
    """Get required environment variable or exit with error."""
    value = os.environ.get(name)
    if not value:
        err_console.print(f"[red]Error:[/red] {name} not set in .env.local")
        raise typer.Exit(1)

    return value


def _check_docker_running() -> None:
    """Check if Docker daemon is running."""
    result = run(["docker", "info"], check=False, capture_output=True)
    if result.returncode != 0:
        err_console.print("[red]Error:[/red] Docker daemon is not running.")
        raise typer.Exit(1)


def _wait_for_postgres(max_attempts: int = 30) -> bool:
    """Wait for PostgreSQL to be ready."""
    import socket

    for attempt in range(max_attempts):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(("localhost", 5432))
            sock.close()

            if result == 0:
                return True
        except Exception:
            pass

        time.sleep(1)

        if attempt % 5 == 0:
            console.print(f"Waiting for PostgreSQL... ({attempt}/{max_attempts})")

    return False


def _get_all_projects() -> list[dict]:
    """Get all projects defined in dg.toml."""
    import tomllib

    dg_toml = SCRIPT_DIR / "dg.toml"
    if not dg_toml.exists():
        return []

    with open(dg_toml, "rb") as f:
        config = tomllib.load(f)

    return config.get("workspace", {}).get("projects", [])


def _get_enabled_projects() -> list[dict]:
    """Get enabled projects based on DEV_PROJECTS env var.

    Returns:
        List of enabled project dicts (each with 'path' key).
        If DEV_PROJECTS is empty/unset, returns all projects.
        If DEV_PROJECTS is set, validates and returns only those projects.

    Raises:
        typer.Exit: If any project in DEV_PROJECTS is not found in dg.toml.
    """
    all_projects = _get_all_projects()
    all_paths: set[str] = {p.get("path") for p in all_projects if p.get("path")}  # type: ignore[misc]

    dev_projects_env = os.environ.get("DEV_PROJECTS", "").strip()

    # Empty or unset means start all projects
    if not dev_projects_env:
        return all_projects

    # Parse comma-separated list
    requested = [p.strip() for p in dev_projects_env.split(",") if p.strip()]

    # Validate all requested projects exist
    for project_name in requested:
        if project_name not in all_paths:
            err_console.print(
                f"[red]Error:[/red] Project '{project_name}' not found in dg.toml"
            )
            err_console.print(f"Available projects: {', '.join(sorted(all_paths))}")
            raise typer.Exit(1)

    # Filter to only requested projects
    return [p for p in all_projects if p.get("path") in requested]


def _sync_subprojects(projects: list[dict] | None = None) -> None:
    """Sync subprojects.

    Args:
        projects: List of project dicts to sync. If None, syncs all from dg.toml.
    """
    if projects is None:
        projects = _get_all_projects()

    if not projects:
        return

    console.print("Syncing subprojects...")

    for project in projects:
        path = project.get("path")
        if path:
            project_dir = SCRIPT_DIR / path
            if project_dir.exists():
                console.print(f"  Syncing [bold]{path}[/bold]...")

                try:
                    env = os.environ.copy()
                    env.pop("VIRTUAL_ENV", None)
                    subprocess.run(["uv", "sync"], check=True, cwd=project_dir, env=env)
                except subprocess.CalledProcessError as e:
                    err_console.print(f"[red]Error:[/red] Failed to sync {path}")
                    raise typer.Exit(1) from e

    console.print("[green]All subprojects synced![/green]")
    console.print()


def _sql_str(value: str) -> str:
    """Quote a value as a SQL string literal."""
    return "'" + value.replace("'", "''") + "'"


def _check_table_name(table: str) -> str:
    """Only allow plain table names, they are placed inside SQL."""
    if not re.fullmatch(r"[A-Za-z0-9_]+", table):
        err_console.print(f"[red]Error:[/red] Invalid table name '{table}'")
        raise typer.Exit(1)

    return table


def _local_lance_uri() -> str:
    return os.environ.get("LANCE_URI") or "./data/lance"


# `pull` asks for confirmation above this many rows when no row limit is given.
PULL_ROW_WARNING = 5_000_000


def _remote_lance_uris() -> dict[str, str]:
    """Remote Lance databases from LANCE_REMOTE_URI, as {name: uri}.

    One plain URI is attached as `remote`. Several are written as comma separated
    `name=uri` pairs, for example
    `ikariam=s3://ikariam/ikariam.lancedb,hackernews=s3://hackernews/lance`,
    and each one is attached under its name.
    """
    remotes: dict[str, str] = {}

    for part in (p.strip() for p in os.environ.get("LANCE_REMOTE_URI", "").split(",")):
        if not part:
            continue

        name, separator, uri = part.partition("=")
        if not separator:
            name, uri = "remote", part

        if not re.fullmatch(r"[a-z][a-z0-9_]*", name) or name == "local" or name in remotes:
            err_console.print(f"[red]Error:[/red] Invalid or duplicate remote name '{name}' in LANCE_REMOTE_URI")
            raise typer.Exit(1)

        remotes[name] = uri

    return remotes


def _s3_secrets_sql(uris: list[str], use_getenv: bool) -> list[str]:
    """One Lance S3 secret per bucket used by the given URIs.

    The credentials come from the environment (AWS_ACCESS_KEY_ID,
    AWS_SECRET_ACCESS_KEY, optional AWS_ENDPOINT_URL and AWS_REGION).
    With use_getenv the SQL reads them itself via getenv(), which only the DuckDB CLI
    offers; this keeps them off the command line. Without it the values are written
    into the SQL, which is fine for the Python client.
    """

    def env_value(name: str) -> str:
        return f"getenv('{name}')" if use_getenv else _sql_str(os.environ[name])

    buckets = []

    for uri in uris:
        if uri.startswith("s3://"):
            bucket = uri.split("/")[2]
            if bucket not in buckets:
                buckets.append(bucket)

    region = _sql_str(os.environ.get("AWS_REGION", "us-east-1"))
    lines = []

    for bucket in buckets:
        options = [
            "TYPE lance",
            "PROVIDER config",
            f"aws_access_key_id {env_value('AWS_ACCESS_KEY_ID')}",
            f"aws_secret_access_key {env_value('AWS_SECRET_ACCESS_KEY')}",
            f"aws_region {region}",
            "aws_virtual_hosted_style_request 'false'",
            f"SCOPE {_sql_str(f's3://{bucket}/')}",
        ]

        if os.environ.get("AWS_ENDPOINT_URL"):
            options.append(f"aws_endpoint {env_value('AWS_ENDPOINT_URL')}")

        lines.append(f"CREATE SECRET lance_{bucket.replace('-', '_')} ({', '.join(options)});")

    return lines


def _require_s3_credentials(uris: list[str]) -> None:
    """Exit with a clear message if an s3:// URI is used without S3 credentials."""
    if not any(uri.startswith("s3://") for uri in uris):
        return

    missing = [
        name
        for name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY")
        if not os.environ.get(name)
    ]
    if missing:
        err_console.print(f"[red]Error:[/red] {', '.join(missing)} not set in .env.local")
        err_console.print(
            "S3 access needs AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in .env.local "
            "(the dev CLI does not read .env). See .env.example."
        )
        raise typer.Exit(1)


def _stale_variables() -> list[str]:
    """DuckLake variables that are no longer used."""
    return sorted(name for name in os.environ if name.startswith("DUCKLAKE_"))


def build_duckdb_init_sql(include_remote: bool = True, use_getenv: bool = True) -> str:
    """Build DuckDB initialization SQL with the local and optionally the remote Lance database attached.

    Tables are then available as local.main.<table> and <remote name>.main.<table>.
    Use use_getenv=False when the SQL runs in the Python client (see _s3_secrets_sql).
    """
    local_uri = _local_lance_uri()
    remotes = _remote_lance_uris() if include_remote else {}

    _require_s3_credentials([local_uri, *remotes.values()])

    if not local_uri.startswith("s3://"):
        Path(local_uri).mkdir(parents=True, exist_ok=True)

    lines = ["INSTALL lance; LOAD lance;", ""]
    lines.extend(_s3_secrets_sql([local_uri, *remotes.values()], use_getenv))
    lines.append(f"ATTACH {_sql_str(local_uri)} AS local (TYPE lance);")

    for name, uri in remotes.items():
        lines.append(f"ATTACH {_sql_str(uri)} AS {name} (TYPE lance);")

    lines.extend(["", "USE local.main;"])

    return "\n".join(lines)


def _create_temp_dg_toml(projects: list[dict]) -> Path:
    """Create a temporary dg.toml with only the specified projects.

    Args:
        projects: List of project dicts to include.

    Returns:
        Path to the directory containing the temp dg.toml.
    """
    # Use a fixed location inside .dagster for visibility
    temp_dir = SCRIPT_DIR / ".dagster" / "dev-workspace"
    temp_dir.mkdir(parents=True, exist_ok=True)

    # Build dg.toml content
    lines = ['directory_type = "workspace"', "", "[workspace]"]

    for project in projects:
        path = project.get("path")
        if path:
            lines.append("[[workspace.projects]]")
            lines.append(f'path = "../../{path}"')
            lines.append("")

    temp_dg_toml = temp_dir / "dg.toml"
    temp_dg_toml.write_text("\n".join(lines))

    return temp_dir


@app.command()
def up():
    """Start Dagster dev environment (native Python, PostgreSQL in Docker)."""
    _check_docker_running()

    # Ensure data directory exists
    (SCRIPT_DIR / "data").mkdir(parents=True, exist_ok=True)
    (SCRIPT_DIR / "data" / "raw").mkdir(parents=True, exist_ok=True)

    # Check for .env.local
    if not ENV_FILE.exists():
        err_console.print(
            "[red]Error:[/red] .env.local not found. "
            "Copy .env.example to .env.local and configure it."
        )
        raise typer.Exit(1)

    # Get enabled projects based on DEV_PROJECTS env var
    all_projects = _get_all_projects()
    enabled_projects = _get_enabled_projects()

    # Show which projects are enabled
    enabled_names: list[str] = [p["path"] for p in enabled_projects if p.get("path")]

    if len(enabled_projects) < len(all_projects):
        console.print(
            f"Enabled projects: [bold]{', '.join(enabled_names)}[/bold] "
            f"({len(enabled_projects)} of {len(all_projects)})"
        )
    else:
        console.print(f"Enabled projects: [bold]all[/bold] ({len(all_projects)})")

    console.print()

    # Sync only enabled subprojects
    _sync_subprojects(enabled_projects)

    # Start PostgreSQL
    console.print("Starting PostgreSQL...")
    docker_compose("up", "-d", "postgresql")

    # Wait for PostgreSQL to be ready
    if not _wait_for_postgres():
        err_console.print("[red]Error:[/red] PostgreSQL failed to start")
        raise typer.Exit(1)

    console.print("[green]PostgreSQL is ready![/green]")

    console.print()
    console.print("Starting Dagster dev server (via dg)...")

    console.print(
        "Open [link=http://localhost:3000]http://localhost:3000[/link] in your browser"
    )

    console.print()

    # Set DAGSTER_HOME to project's .dagster/home directory
    dagster_home = SCRIPT_DIR / ".dagster" / "home"
    dagster_home.mkdir(parents=True, exist_ok=True)
    os.environ["DAGSTER_HOME"] = str(dagster_home)

    # Create dagster.yaml for dev using PostgreSQL storage (avoids SQLite locking issues)
    dagster_yaml = dagster_home / "dagster.yaml"

    dagster_yaml.write_text(
        "storage:\n"
        "  postgres:\n"
        "    postgres_db:\n"
        "      username: dagster_user\n"
        "      password: dagster_password\n"
        "      hostname: localhost\n"
        "      db_name: dagster_db\n"
        "      port: 5432\n"
        "\n"
        "telemetry:\n"
        "  enabled: false\n"
    )

    # Create temp dg.toml with only enabled projects and run dg dev from there
    if len(enabled_projects) < len(all_projects):
        temp_dir = _create_temp_dg_toml(enabled_projects)
        raise typer.Exit(run_foreground(["dg", "dev", "--target-path", str(temp_dir)]))
    else:
        # All projects enabled, use normal dg.toml
        raise typer.Exit(run_foreground(["dg", "dev"]))


@app.command()
def down():
    """Stop PostgreSQL container."""
    docker_compose("down")


@app.command()
def prod():
    """Start production-like environment (full Docker stack)."""
    _check_docker_running()

    # Ensure bind-mounted data directories exist with the current user as owner.
    (SCRIPT_DIR / "data").mkdir(parents=True, exist_ok=True)
    (SCRIPT_DIR / "data" / "raw").mkdir(parents=True, exist_ok=True)

    # Check for .env.local
    if not ENV_FILE.exists():
        err_console.print(
            "[red]Error:[/red] .env.local not found. "
            "Copy .env.example to .env.local and configure it."
        )
        raise typer.Exit(1)

    # Generate production compose
    console.print("Generating production config...")
    run(["uv", "run", "python", "generate_platform.py"])

    console.print()
    console.print("Starting production environment...")
    console.print(
        "Open [link=http://localhost:3000]http://localhost:3000[/link] in your browser"
    )
    console.print()

    raise typer.Exit(
        run_foreground(["docker", "compose", "-f", PROD_COMPOSE, "up", "--build"])
    )


@app.command()
def new(
    name: str = typer.Argument(
        ..., help="Name for the new project (lowercase, underscores)"
    ),
):
    """Create a new project (Dagster code location) from template."""
    # Validate name
    if not re.match(r"^[a-z][a-z0-9_]*$", name):
        err_console.print(
            "[red]Error:[/red] Project name must be lowercase, start with a letter, "
            "and contain only letters, numbers, and underscores."
        )
        raise typer.Exit(1)

    dest = SCRIPT_DIR / name
    if dest.exists():
        err_console.print(
            f"[red]Error:[/red] Project '{name}' already exists at {dest}"
        )
        raise typer.Exit(1)

    console.print(f"Creating new project: [bold]{name}[/bold]")

    # Copy template
    template_dir = SCRIPT_DIR / "_template"
    if not template_dir.exists():
        err_console.print(
            f"[red]Error:[/red] Template directory not found at {template_dir}"
        )
        raise typer.Exit(1)

    shutil.copytree(template_dir, dest)

    # Replace placeholders in all files
    for file_path in dest.rglob("*"):
        if file_path.is_file():
            try:
                content = file_path.read_text()
                # Replace __name__ placeholder
                content = content.replace("__name__", name)
                content = content.replace("__NAME__", name.upper())
                file_path.write_text(content)
            except UnicodeDecodeError:
                # Skip binary files
                pass

    # Rename src/__name__ directory if it exists
    name_dir = dest / "src" / "__name__"
    if name_dir.exists():
        name_dir.rename(dest / "src" / name)

    # Generate lock file
    console.print("Generating lock file...")
    run(["uv", "lock"], cwd=dest)

    # Add to dg.toml
    dg_toml = SCRIPT_DIR / "dg.toml"
    if dg_toml.exists():
        content = dg_toml.read_text()
        if f'path = "{name}"' not in content:
            content += f'\n[[workspace.projects]]\npath = "{name}"\n'
            dg_toml.write_text(content)

    console.print()
    console.print(f"[green]Project '{name}' created at {dest}[/green]")
    console.print()
    console.print("Next steps:")
    console.print(f"  1. Add your assets in {dest}/src/{name}/assets/")
    console.print(f"  2. Update {dest}/src/{name}/definitions.py")
    console.print(f"  3. Add any dependencies to {dest}/pyproject.toml")
    console.print("  4. Run [bold]just up[/bold] to start the dev environment")


@app.command()
def logs(
    service: Optional[str] = typer.Argument(
        None, help="Specific service to view logs for"
    ),
):
    """View logs (optionally for specific service)."""
    cmd = ["docker", "compose", "logs", "-f"]
    if service:
        cmd.append(service)
    raise typer.Exit(run_foreground(cmd))


@app.command()
def db(
    local_only: bool = typer.Option(
        False, "--local-only", "-l", help="Only attach local database (skip remote)"
    ),
    file: str | None = typer.Option(
        None, "--file", "-f", help="Run this SQL file and exit (path from the repository root)"
    ),
):
    """Open interactive DuckDB session (local + remote Lance databases attached).

    With --file, run one SQL file in that session and print the results instead.

    Requires the DuckDB CLI (version 2.0 or newer, for the core lance extension):
    - macOS: brew install duckdb
    - Windows: winget install DuckDB.cli
    - Linux: https://duckdb.org/docs/installation/
    """
    # Check if duckdb CLI is available
    if not shutil.which("duckdb"):
        err_console.print("[red]Error:[/red] DuckDB CLI not found.")
        err_console.print("Install it separately:")
        err_console.print("  macOS:   brew install duckdb")
        err_console.print("  Windows: winget install DuckDB.cli")
        err_console.print("  Linux:   https://duckdb.org/docs/installation/")
        raise typer.Exit(1)

    sql_file = None
    if file is not None:
        sql_file = (SCRIPT_DIR / file).resolve()
        if not sql_file.is_file():
            err_console.print(f"[red]Error:[/red] SQL file not found: {file}")
            raise typer.Exit(1)

    sql = build_duckdb_init_sql(include_remote=not local_only)

    local_uri = _local_lance_uri()
    remotes = _remote_lance_uris()
    console.print(f"local:  {local_uri}")

    if local_only:
        console.print("remote: skipped (--local-only)")
    elif remotes:
        for name, uri in remotes.items():
            console.print(f"{name}: {uri}")
    else:
        console.print(
            "[yellow]remote: not configured[/yellow] "
            "(set LANCE_REMOTE_URI and the AWS_* keys in .env.local, see .env.example)"
        )

    stale = _stale_variables()
    if stale:
        console.print(
            f"[yellow]Ignoring unused DuckLake variables in .env.local:[/yellow] {', '.join(stale)}"
        )

    if sql_file is not None:
        raise typer.Exit(run_foreground(["duckdb", "-cmd", sql, "-f", str(sql_file)]))

    console.print("Tables: SHOW ALL TABLES;  (local tables are also reachable without a prefix)")
    console.print()

    raise typer.Exit(run_foreground(["duckdb", "-cmd", sql]))


@app.command("export")
def export_table(
    table: str = typer.Argument(..., help="Table name to export"),
    format: str = typer.Argument(
        "parquet", help="Export format: parquet, csv, json, ndjson"
    ),
    source: str = typer.Argument("local", help="Data source: local or the name of a remote"),
):
    """Export table to local file."""
    # Validate format
    format_map = {
        "parquet": ("parquet", "FORMAT PARQUET"),
        "csv": ("csv", "FORMAT CSV, HEADER"),
        "json": ("json", "FORMAT JSON, ARRAY true"),
        "ndjson": ("ndjson", "FORMAT JSON"),
    }

    if format not in format_map:
        err_console.print(f"[red]Error:[/red] Unknown format '{format}'")
        err_console.print("Supported formats: parquet, csv, json, ndjson")
        raise typer.Exit(1)

    remotes = _remote_lance_uris()
    if source != "local" and source not in remotes:
        err_console.print(
            f"[red]Error:[/red] Unknown source '{source}'. "
            f"Available: {', '.join(['local', *remotes]) or 'local'} (remotes come from LANCE_REMOTE_URI)"
        )
        raise typer.Exit(1)

    _check_table_name(table)
    ext, format_opts = format_map[format]
    output_file = f"{table}.{ext}"
    source_table = f"{source}.main.{table}"

    conn = duckdb.connect()
    conn.execute(build_duckdb_init_sql(use_getenv=False))

    conn.execute(
        f"COPY (SELECT * FROM {source_table}) TO {_sql_str(output_file)} ({format_opts})"
    )

    result = conn.execute(f"SELECT COUNT(*) FROM {source_table}").fetchone()
    row_count = result[0] if result else 0
    console.print(f"{output_file}: {row_count} rows exported from {source}")


def _pull_table(conn: duckdb.DuckDBPyConnection, database: str, table: str, limit: Optional[int]) -> None:
    """Copy one remote table into the local Lance database, replacing any older local copy."""
    target = f"{_local_lance_uri().rstrip('/')}/{table}.lance"
    query = f"SELECT * FROM {database}.main.{table}"

    if limit:
        query += f" LIMIT {int(limit)}"

    conn.execute(f"COPY ({query}) TO {_sql_str(target)} (FORMAT lance, mode 'overwrite')")

    result = conn.execute(f"SELECT COUNT(*) FROM local.main.{table}").fetchone()
    row_count = result[0] if result else 0
    console.print(f"{table}: {row_count} rows pulled from {database}")

    # Mark asset as materialized in native Dagster instance
    _mark_asset_materialized(table, "Pulled from remote Lance database")


def _row_count(conn: duckdb.DuckDBPyConnection, database: str, table: str) -> int:
    """Row count from the Lance metadata, so this is quick even for huge tables."""
    result = conn.execute(f"SELECT COUNT(*) FROM {database}.main.{table}").fetchone()
    return result[0] if result else 0


@app.command()
def pull(
    table: Optional[str] = typer.Argument(
        None, help="Table to pull (omit to list tables)"
    ),
    limit: Optional[int] = typer.Argument(None, help="Limit number of rows to pull"),
    source: Optional[str] = typer.Option(
        None, "--from", "-f", help="Name of the remote database (if there are several)"
    ),
    database: Optional[str] = typer.Option(
        None, "--db", "-d", help="Pull every table of this remote database"
    ),
    yes: bool = typer.Option(
        False, "--yes", "-y", help=f"Pull tables of more than {PULL_ROW_WARNING:,} rows without a row limit"
    ),
):
    """List remote tables, pull one table, or pull a whole remote database.

    Pulling again replaces the local copy, so it also brings in changes made on the server.
    """
    remotes = _remote_lance_uris()
    if not remotes:
        err_console.print("[red]Error:[/red] LANCE_REMOTE_URI not set in .env.local")
        raise typer.Exit(1)

    for name in (source, database):
        if name is not None and name not in remotes:
            err_console.print(f"[red]Error:[/red] Unknown remote '{name}'. Available: {', '.join(remotes)}")
            raise typer.Exit(1)

    if database is not None and source is not None:
        err_console.print("[red]Error:[/red] Use either --db or --from, not both.")
        raise typer.Exit(1)

    conn = duckdb.connect()
    conn.execute(build_duckdb_init_sql(use_getenv=False))

    searched = [database or source] if (database or source) else list(remotes)
    names = ", ".join(_sql_str(name) for name in searched)

    found = conn.execute(
        f"SELECT database, name FROM (SHOW ALL TABLES) WHERE database IN ({names}) ORDER BY database, name"
    ).fetchall()

    # Whole database: --db <name>, optionally with a row limit per table as the only argument.
    if database is not None:
        if table is not None and limit is None and table.isdigit():
            table, limit = None, int(table)

        if table is not None:
            err_console.print("[red]Error:[/red] With --db, give no table name (only an optional row limit).")
            raise typer.Exit(1)

        tables = [name for _, name in found]
        if not tables:
            err_console.print(f"[red]Error:[/red] No tables found in {database}")
            raise typer.Exit(1)

        if not limit and not yes:
            large = [(name, _row_count(conn, database, name)) for name in tables]
            large = [(name, n) for name, n in large if n > PULL_ROW_WARNING]
            if large:
                for name, n in large:
                    err_console.print(f"[red]Error:[/red] {database}.{name} has {n:,} rows.")
                err_console.print(
                    f"Give a row limit per table (for example 'just pull --db {database} 10000') or confirm with --yes."
                )
                raise typer.Exit(1)

        console.print(f"Pulling {len(tables)} tables from {database}")
        for name in tables:
            _pull_table(conn, database, name, limit)
        return

    if table is None:
        console.print("Remote tables:")
        for db_name, name in found:
            console.print(name if len(remotes) == 1 else f"{db_name}.{name}")
        return

    _check_table_name(table)
    sources = [db_name for db_name, name in found if name == table]
    if not sources:
        err_console.print(f"[red]Error:[/red] Table '{table}' not found in {', '.join(searched)}")
        raise typer.Exit(1)

    if len(sources) > 1:
        err_console.print(f"[red]Error:[/red] Table '{table}' exists in {', '.join(sources)}. Choose one with --from.")
        raise typer.Exit(1)

    if not limit and not yes:
        total = _row_count(conn, sources[0], table)
        if total > PULL_ROW_WARNING:
            err_console.print(
                f"[red]Error:[/red] {sources[0]}.{table} has {total:,} rows and would be copied completely."
            )
            err_console.print(
                f"Give a row limit (for example 'just pull {table} 10000') or confirm with --yes."
            )
            raise typer.Exit(1)

    _pull_table(conn, sources[0], table, limit)


@app.command()
def mark(
    assets: str = typer.Argument(
        ..., help="Comma-separated list of asset names to mark"
    ),
):
    """Mark assets as materialized without running them."""
    for asset_name in assets.split(","):
        asset_name = asset_name.strip()
        _mark_asset_materialized(asset_name, "Manually marked as materialized")


def _mark_asset_materialized(asset_name: str, description: str) -> None:
    """Mark an asset as materialized in the native Dagster instance."""
    try:
        from dagster import DagsterInstance, AssetKey, AssetMaterialization

        instance = DagsterInstance.get()
        key = AssetKey(asset_name)

        instance.report_runless_asset_event(
            AssetMaterialization(
                asset_key=key,
                description=description,
                metadata={"source": "dev cli"},
            )
        )

        console.print(f"Marked {asset_name} as materialized")
    except Exception as e:
        err_console.print(f"[yellow]Warning:[/yellow] Could not mark {asset_name}: {e}")


def main():
    """Entry point for the CLI."""
    os.chdir(SCRIPT_DIR)
    app()
