FROM my-platform-base:latest

# Copy dependency files first (for caching)
COPY pyproject.toml uv.lock* ./

# Install Python dependencies
RUN uv sync --frozen || uv sync

# Copy the rest of the project
COPY . .

# Run the Dagster gRPC server
CMD ["uv", "run", "dagster", "api", "grpc", "-h", "0.0.0.0", "-p", "4000", "-f", "repo/defs.py"]
