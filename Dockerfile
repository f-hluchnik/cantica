FROM python:3.13-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN apt-get update && apt-get install -y --no-install-recommends gosu && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
RUN CANTICA_ENV=production SECRET_KEY=build-only python manage.py collectstatic --noinput
RUN useradd --create-home --uid 1000 appuser && chown -R appuser:appuser /app
EXPOSE 8000
CMD ["/app/bin/start.sh"]
