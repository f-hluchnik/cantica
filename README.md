# Directus Cantica

Online direktář pro varhaníky: the liturgical calendar plus song recommendations from Kancionál,
following *Direktář pro varhaníky*. Design: [docs/design-v2.md](docs/design-v2.md).

Status: **v2, milestone M2** — calendar (M1) and the song catalog with curation in the admin (M2).
Song recommendations arrive in M3.

## Local development

```sh
python3.13 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
DEBUG=1 python manage.py migrate
DEBUG=1 python manage.py curation_import --if-empty   # songs and groups from data/curated/
DEBUG=1 python manage.py calendar_build               # needs data/, see below
DEBUG=1 python manage.py createsuperuser              # for /admin/
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

## Curated data (songs, groups; rules from M3)

Unlike the calendar, curated data is **edited in the admin**; the DB is the source of truth and
`data/curated/curation.yaml` is its export (backup, review, tests).

| command | what it does |
|---|---|
| `curation_export [--print]` | write the DB to the YAML and mark the DB as exported |
| `curation_import [--if-empty] [--force]` | replace the curated tables with the YAML; refuses if the DB has unexported changes |

Every admin save bumps a version counter (admin → *Stav kurátorských dat*). A weekly Action exports
production and opens a PR. To push hand edits of the YAML to production: merge them, then
`fly ssh console -C "gosu appuser python /app/manage.py curation_import"` (refused if the admin has unexported changes).

Song verse fields (*k přijímání*, *na závěr*): empty = not verified, `-` = none, `*` = as dedicated in
Kancionál, `4,5` = these verses. The admin song list can filter by each state.

The catalog (511 entries, codes as on kancional.cz) was transcribed from kancional.cz/ciselny-seznam on
2026-10-30; the v1 communion/recessional flags were carried over as `*`, and *mešní píseň* was pre-set for
131 songs (members of the mass groups plus every song v1 used as the main mass song). All of it is `reviewed: false`.

## Deployment (Fly.io)

- `fly.toml` = production (`directuscantica.cz`), `fly.test.toml` = test instance (`test.directuscantica.cz`).
- SQLite lives on a Fly volume mounted at `/data`; one machine, always on.
- `bin/start.sh` runs `migrate`, `curation_import --if-empty` and `calendar_build` on start (Fly's release
  machine cannot see the volume), then gunicorn. A failing build keeps the previous data and the site stays up.
- Run management commands on Fly **as appuser** (`gosu appuser python /app/manage.py …`), never as root:
  SQLite files created by root would make the database read-only for the app.
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
