FROM my-platform-base:latest

# Copy shared code first
COPY _shared/ /opt/dagster/app/_shared/

# Copy dependency files (for caching)
# NOTE: Replace 'my_pipeline' with your pipeline name
COPY my_pipeline/pyproject.toml my_pipeline/uv.lock* ./

# Install Python dependencies
RUN uv sync --frozen || uv sync

# Copy the pipeline code
# NOTE: Replace 'my_pipeline' with your pipeline name
COPY my_pipeline/assets/ ./assets/
COPY my_pipeline/defs.py ./

# Run the Dagster gRPC server
CMD ["uv", "run", "dagster", "api", "grpc", "-h", "0.0.0.0", "-p", "4000", "-f", "defs.py"]
