# Use official Python image as base
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100

WORKDIR /app

# Install system dependencies
# curl is needed for healthchecks; remove gcc/libpq-dev once you're off Postgres
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Collect static files at build time (files are baked into the image)
# SECRET_KEY is a dummy — only needed so Django settings load without error
RUN SECRET_KEY=dummy-build-key DEBUG_VALUE=dummy-debug-value python manage.py collectstatic --noinput --clear

# Run as non-root user for security
RUN useradd --no-create-home appuser && chown -R appuser /app
USER appuser

EXPOSE 8000

# Workers: 2*CPUs+1 is the standard Gunicorn recommendation
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--timeout", "120", "cantica.wsgi:application"]