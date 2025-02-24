# Use official Python image as base
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libpq-dev gcc curl && \
    rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Set permissions for security
RUN chmod -R 755 /app

# Expose port 8000 (Gunicorn default)
EXPOSE 8000

# Run collectstatic at runtime, before Gunicorn starts
CMD ["sh", "-c", "python manage.py collectstatic --noinput --clear && gunicorn --bind 0.0.0.0:8000 cantica.wsgi:application"]
