# Use a lightweight python base image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" \
    PORT=5050 \
    HOST=0.0.0.0

# Install uv for fast, reliable package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Copy dependency files first for efficient caching
COPY pyproject.toml uv.lock ./

# Install dependencies into a virtual environment (.venv)
RUN uv sync --frozen --no-cache --no-install-project

# Copy the rest of the application code
COPY . .

# Expose the port FastAPI runs on
EXPOSE 5050

# Default command to run the web server
CMD ["python", "web_server.py"]
