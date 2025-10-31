# Dockerfile
FROM python:3.14-alpine

# Optional build deps if you later add wheels that need compiling
# RUN apk add --no-cache build-base

# Use uv to manage deps
RUN pip install --no-cache-dir uv

WORKDIR /app

# Copy project metadata first to leverage layer caching
COPY pyproject.toml uv.lock* ./

# Install only prod deps into a local .venv
RUN uv sync --no-dev --group prod

# Put the venv on PATH so gunicorn resolves
ENV PATH="/app/.venv/bin:${PATH}"

# Copy the rest of your app
COPY . .

# Non-root user is fine if your app reads needed files
RUN addgroup -S app && adduser -S -G app app
USER app

EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "-b", "0.0.0.0:8000"]
