# Directus Cantica

Online direktář pro varhaníky: the liturgical calendar plus song recommendations from Kancionál,
following *Direktář pro varhaníky*. Design: [docs/design-v2.md](docs/design-v2.md).

Status: **v2, milestone M1** — calendar only (ranked celebrations, liturgical colours,
Sláva / Věřím / Aleluja, dioceses). Song recommendations arrive in M3.

## Local development

```sh
python3.13 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
DEBUG=1 python manage.py migrate
DEBUG=1 python manage.py calendar_build      # needs data/, see below
DEBUG=1 python manage.py runserver
```

Checks (the same ones CI runs):

```sh
ruff check .
python manage.py makemigrations --check --dry-run
python manage.py test tests                        # all tests
python -m unittest discover -s tests/unit -t .     # pure tests only, no Django needed
```

## Calendar data

The site never calls the calendar API at runtime. Data flows like this:

```
calapi ──calendar_sync──► data/calendar/raw/<calendar>/<yyyy-mm>.json   (git)
                          data/liturgy/celebrations.yaml                 (git, celebration identity)
                ──calendar_build──► SQLite (rebuilt on every start if data/ changed)
```

| command | what it does | touches DB |
|---|---|---|
| `calendar_sync [--start YYYY-MM] [--end YYYY-MM] [--calendar czech …]` | fetch months (default: last month .. +24), write only changed files | no |
| `calendar_catalog [--register-new]` | check that every non-feria title is in the catalog; optionally add new ones and print possible duplicates | no |
| `calendar_build [--check] [--force]` | validate everything and rebuild the calendar tables; writes nothing if any problem is found | yes (not with `--check`) |

A GitHub Action runs the sync monthly and opens a PR. When a PR adds celebrations, check the
"possible duplicate" hints: if a new title is a variant of an existing celebration, move it into
that entry's `aliases` and delete the new entry. Keys are permanent once a rule refers to them.

### First-time bootstrap (v2 starts with an empty `data/`)

```sh
python manage.py calendar_sync --start 2025-10            # all 11 calendars; takes a few minutes
python manage.py calendar_catalog --register-new          # creates the catalog, review the hints
python manage.py calendar_build
git add data && git commit -m "calendar: initial data"
```

## Deployment (Fly.io)

- `fly.toml` = production (`directuscantica.cz`), `fly.test.toml` = test instance (`test.directuscantica.cz`).
- SQLite lives on a Fly volume mounted at `/data`; one machine, always on.
- `bin/start.sh` runs `migrate` and `calendar_build` on start (Fly's release machine cannot see the volume),
  then gunicorn. A failing `calendar_build` keeps the previous data and the site stays up.
- Push to `main` → CI → deploy. Any branch can go to the test instance via the "Deploy test instance" workflow.
- `/live` is the Fly health check; `/health` reports calendar freshness and is checked daily by an Action.

One-time setup:
- per Fly app: `fly volumes create …`, `fly secrets set SECRET_KEY=…` (see the comments in the toml files);
- GitHub secrets: `FLY_API_TOKEN` (production), `FLY_API_TOKEN_TEST` (test app);
- GitHub → Settings → Actions → General: enable "Allow GitHub Actions to create and approve pull requests"
  (needed by the calendar-sync workflow).

## Environment variables

`CANTICA_ENV` (`production` on Fly), `DEBUG`, `SECRET_KEY`, `ALLOWED_HOSTS`, `DATABASE_PATH`,
`SENTRY_DSN` (optional), `UMAMI_WEBSITE_ID` (optional). See `cantica/settings.py`.
