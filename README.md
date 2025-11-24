# dumping prod db
- fly ssh console -a directus-cantica-db
- inside container `psql postgres://postgres:$OPERATOR_PASSWORD@directus-cantica-db.internal:5432`
- inside psql: `\! pg_dump -Fc postgres://postgres:$OPERATOR_PASSWORD@localhost:5432/directus_cantica > prod.dump`
- the `\q`
- then import in local DB:
```
pg_restore \
  --clean \
  --no-owner \
  --no-privileges \
  -d postgres://devuser:devpass@localhost:5432/devdb \
  prod.dump
```

# loading new liturgical calendar events
- fly ssh console -a directus-cantica
- python manage.py shell
- from celebrations.utils.liturgy_api_client import LiturgyAPIClient
- client = LiturgyAPIClient()
- client.fetch_month(year=2026, month=11)