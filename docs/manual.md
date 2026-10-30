# Directus Cantica – operator's manual

How the app works, where its data lives, and how to run it day to day. For *why* things are built this way,
see [design-v2.md](design-v2.md); this manual is the practical part.

Contents:
1. [The mental model](#1-the-mental-model)
2. [Where things are (repository map)](#2-where-things-are)
3. [The three kinds of data](#3-the-three-kinds-of-data)
4. [Rules and how a day page is computed](#4-rules-and-how-a-day-page-is-computed)
5. [Status fields ("verified", "reviewed")](#5-status-fields-verified-reviewed)
6. [Environments: local, test, production](#6-environments)
7. [Everyday recipes](#7-everyday-recipes)
8. [Releasing code](#8-releasing-code)
9. [Automatic jobs (GitHub Actions)](#9-automatic-jobs-github-actions)
10. [Fly.io operations](#10-flyio-operations)
11. [Troubleshooting](#11-troubleshooting)
12. [Reference](#12-reference)

---

## 1. The mental model

The app answers one question: *which Kancionál songs fit this mass?* It does that in three steps.

```
 ┌─────────────────────────┐   ┌────────────────────────────┐   ┌──────────────────────────┐
 │ 1. CALENDAR (git)       │   │ 2. CURATED DATA (prod DB)  │   │ 3. ENGINE (pure Python)  │
 │ what is celebrated when │ + │ songs, song groups, rules  │ → │ rules × day → songs      │
 │ calapi → data/ → DB     │   │ edited in /admin/          │   │ summary + detailed plan  │
 └─────────────────────────┘   └────────────────────────────┘   └──────────────────────────┘
```

- **The calendar** comes from calapi.inadiutorium.cz, but the site never calls calapi at runtime. A monthly
  job saves calapi's answers as JSON files in git, and the app builds its calendar tables from those files when
  it starts.
- **The curated data** consists of 511 songs, about 16 song groups and about 300 rules. You edit it in the
  admin, and the production database is its source of truth. `data/curated/curation.yaml` is a copy (export)
  of it in git, used for backups, reviewing changes, tests, and seeding a new database.
- **The engine** (`engine/`) is plain Python with no Django inside. Given one day and the rules, it returns
  the recommendations for each mass. The website, the JSON API, the admin preview, the lint command and the
  tests all use this same engine.

Some consequences of this split:

- A **new or empty database is never a disaster.** On start the app rebuilds the calendar from git and imports
  `curation.yaml`. The only things that exist in the production database alone are admin users and curated
  edits made since the last export.
- **Code changes** reach production through git (push to `main`). **Rule and song changes** are made in the
  admin and take effect at the next page load, with no deploy needed.
- Every admin save increases a **version counter**. A weekly job exports the database to git and opens a PR,
  so git always holds a recent copy.

## 2. Where things are

| Path | What it is |
|---|---|
| `engine/` | The recommendation engine (pure): `resolve.py` matches rules per mass part, `plan.py` builds the *detailní doporučení*, `recommend.py` is the entry point, `context.py` turns calendar days into engine input (and adds the first-Friday votive mass), `vocab.py` holds the vocabulary (mass parts, strengths, tiers). |
| `liturgy/` | Calendar: calapi client, raw snapshots, celebration catalog, building the DB tables, liturgical norms (Gloria, Credo), periods, category heuristic. |
| `catalog/` | Songs and groups: models, admin, YAML import/export (`dbsync.py`, `curation.py`). |
| `rules/` | Rules: model, admin (with a preview of the dates a rule applies to), `services.py` (cache plus the link between DB and engine), `rules_lint`. |
| `web/` | Views, templates, CSS/JS, JSON API (`api.py`). |
| `data/calendar/raw/` | calapi answers, one JSON file per calendar and month (git). |
| `data/liturgy/celebrations.yaml` | Celebration catalog: a permanent key for every celebration title, aliases, categories. |
| `data/liturgy/periods.yaml` | Named date ranges for rules (late Advent, May, unity week…). |
| `data/curated/curation.yaml` | Export of songs, groups and rules (git copy of the production database). |
| `tests/unit/` | Fast tests without Django. |
| `tests/book/` | "Book assertions": the real engine on the committed data, checking what the Direktář says. |
| `tests/integration/` | Django tests (views, admin, commands). |
| `bin/start.sh` | Container start script: migrate, build the calendar, import curation if the DB is empty, start gunicorn. |
| `fly.toml`, `fly.test.toml` | Fly.io configuration for production and test. |
| `docs/design-v2.md` | Design and the record of decisions (§15–17: what changed in M3–M5). |
| `docs/design-archive/` | Previous UI designs, kept for reference. |

## 3. The three kinds of data

| Data | Source of truth | Edited how | Reaches production how |
|---|---|---|---|
| Calendar days (what is celebrated, rank, colour) | `data/calendar/raw/` in git | never by hand; the monthly sync job | merge the "Calendar sync" PR → deploy → rebuilt on start |
| Celebration catalog, categories, periods | `data/liturgy/*.yaml` in git | by hand in the YAML (or via the sync PR for new titles) | merge → deploy → rebuilt on start |
| Songs, groups, rules | **production DB** | admin `/admin/` | immediately |
| Admin users | production DB | `createsuperuser` / admin | — (never in git) |

### 3.1 Calendar

```
calapi ──calendar_sync──► data/calendar/raw/<calendar>/<yyyy-mm>.json   (git)
                ──calendar_build──► calendar tables in SQLite             (on every start, only if data/ changed)
```

- There are 11 calendars: the general Czech one, Čechy, Morava, and one per diocese. The diocese selector on
  the site chooses which one is shown.
- Every celebration title must map to a key in `celebrations.yaml`. Rules point to these keys (for example
  `sv-vaclava-mucednika-hlavniho-patrona-ceskeho-naroda`), so **a key never changes once a rule uses it**.
- `calendar_build` validates everything first and writes nothing if any problem is found. A broken data commit
  therefore leaves the previous calendar in place and the site keeps running.
- The data reaches about 24 months ahead. `/health` reports `warn` once fewer than 180 days remain.

### 3.2 Celebration categories

Categories decide the ■ tier (Direktář pp. 8–9): `lord`, `virgin_mary`, `apostle_evangelist`, `martyr`,
`pastor`, `woman`, `saint`, `czech_patron`, `dedication`, … A title heuristic suggests them
(`liturgy/categorize.py`). Once you have checked an entry, set `categories_reviewed: true` and the heuristic
leaves it alone from then on.

### 3.3 Curated data and the version counter

- Each save in the admin (song, group or rule) bumps `CurationState.version`. You can see it under *Stav
  kurátorských dat*.
- `exported_version` records which version git has seen. If `version > exported_version`, the database holds
  **unexported changes**.
- `curation_import` (YAML → DB) **refuses** to overwrite unexported changes unless you add `--force`. This
  protects work done in the admin from being replaced by an older file.

## 4. Rules and how a day page is computed

### 4.1 A rule

A rule is one clause of the Direktář, or an author's convention when it has no page (shown as *doporučení
autora*).

| Field | Meaning |
|---|---|
| **Kdy** (scope) | the most specific field that is set decides the tier: *slavení* (celebration key) → ▲, *kategorie* → ■, *období* (period) / *liturgická doba* (season) / nothing → ●. Every field that is set must match. *Příležitost* (occasion) rules never apply to calendar days; they feed `/prilezitosti/`. |
| filters | Sunday cycles (A/B/C), Sunday / weekday, minimal rank, dioceses |
| **části mše** | parts the rule talks about: mešní píseň, ke vstupu, před evangeliem, k obětnímu průvodu, k přijímání, díkůvzdání po přijímání, na závěr, před mší, and the special ones (sekvence, kropení, …) |
| **druh** | *písně* (songs), *písně ze svátků okolních dnů* (songs from nearby feasts), *poznámka* (note), *nic se nezpívá* (silence) |
| **síla** | *předepsáno* (prescribed) > *doporučeno* (recommended) > *možno též* (also possible) — and *nevhodné* (avoid), which removes songs. An avoid rule only wins against rules at the same or a lower tier. |
| **písně** | `523` · `813B` · `Z781` (HK appendix) · `838/5` (verse) · `838/1+3` · `691-695` (range) · `@mesni_obecne` (group) · `#advent` (Kancionál section) |
| **jen bez vlastní písně** | (*fallback*) the rule drops out when a more specific rule gives the same part a song; for example 840/841 apply only to saints without a song of their own |
| strana Direktáře | the page; leave it empty for an author rule |

The rule's change form shows the next dates it applies to, with links, so you can check a change right away.

### 4.2 From a day to the page

For every mass option of the day (a feast, the optional memorial, the plain weekday, the first-Friday votive
mass…):

1. **Match** the rules: scope plus filters for that day and celebration.
2. **Resolve each part**: collect candidate songs, remove avoided ones, and merge songs named by several
   rules. A merged song keeps the highest tier and strength, so 910 on 18. 1. becomes ▲ *předepsáno*.
3. **Summary** (always visible): everything ▲/■, everything prescribed, and for the mass song the season's
   label (*Adventní písně*, *mešní písně obecné*…). Single ● songs are not listed; they only steer the plan.
4. **Detailní doporučení**: one deterministic combination. It changes from week to week but is identical on
   every reload:
   - either a mešní píseň, or one song per part (late Advent);
   - k přijímání / na závěr get their own line only when a better-fitted song exists; otherwise the mass song
     continues;
   - *díkůvzdání* appears only with a specific (▲/■) or prescribed song.
5. **Notes**: notes from ● rules (season, period) go into the small box above the cards. Notes from ▲/■
   rules stay in their card.

Special cases worth knowing:

- **Saturday and 24 December** also show the next day's masses (the evening mass).
- **First Friday** in Ordinary Time, with no obligatory memorial or higher, adds a votive-mass card (celebration
  key `prvni-patek`).
- **Neighbour songs** (*písně ze svátků okolních dnů*, p. 27) are not used on feasts, solemnities and All
  Souls.

### 4.3 Checking the whole ruleset

```sh
python manage.py rules_lint              # the local DB
python manage.py rules_lint --file       # data/curated/curation.yaml
python manage.py rules_lint --coverage   # + celebrations without a ▲/■ mass song
```

The lint runs the real matching over about 12 000 calendar days. It reports unknown references, contradictions
(a recommendation and an avoid of the same song at the same level, both from the Direktář) and rules that
never apply. An author rule overriding the Direktář is reported as an *override*, not as an error. A few
"never applies" warnings for Sunday-cycle rules are expected: they belong to Sundays that a solemnity replaces
within the data window.

## 5. Status fields ("verified", "reviewed")

There are four kinds. Only the first one changes what the site recommends.

| Field | Where | Effect on recommendations |
|---|---|---|
| **Verse fields** *k přijímání* / *na závěr* (`communion_verses`, `recessional_verses`): empty = **not verified**, `-` = none, `*` = as marked in Kancionál, `4,5` = these verses | admin → Písně | **Yes.** A section like `#jesus` offers a song k přijímání / na závěr only if it has a verified verse for that part. The mass song "continues" at communion only if it has a verified communion verse. |
| **mešní píseň** (`mass_song`): yes / no / empty (unknown) | admin → Písně | **Yes.** `#section` targets for *mešní píseň* use only songs marked *yes*; a song marked *no* is never offered as mešní píseň, even when named explicitly. |
| **zkontrolováno** (`reviewed`) on songs | admin → Písně | **No.** It's a checklist for you: tick it once you have checked a song's data against the Kancionál. The admin list can filter by it. |
| **categories_reviewed** on celebrations | `celebrations.yaml` | **No** direct effect. It protects your checked categories from the heuristic, and a test makes sure unreviewed entries always match the heuristic. |

In practice: **verse fields and *mešní píseň* matter**, and filling them in improves the plan. The
*reviewed* flags are only bookkeeping.

## 6. Environments

| | Local | Test | Production |
|---|---|---|---|
| URL | http://127.0.0.1:8000 | https://test.directuscantica.cz | https://directuscantica.cz |
| Fly app | — | `directus-cantica-test` | `directus-cantica` |
| Database | `db.sqlite3` in the repo (git-ignored) | volume `cantica_test_data` | volume `cantica_data` |
| Code | your working tree | any branch, deployed by hand | `main`, deployed automatically |
| Curated data | whatever you imported | a copy (from git or from production) | **the original** |
| Running | when you start it | **only when you start it** | always (one machine) |

### 6.1 Local

```sh
python3.13 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
DEBUG=1 python manage.py migrate
DEBUG=1 python manage.py calendar_build
DEBUG=1 python manage.py curation_import --if-empty
DEBUG=1 python manage.py createsuperuser
DEBUG=1 python manage.py runserver
```

With `DEBUG=1` pages are never cached, so template and CSS edits show on reload. To refresh your local
curated data from git: `DEBUG=1 python manage.py curation_import --force`.

### 6.2 Test instance

**It doesn't wake up by itself.** `auto_start_machines = false`: the machine stops a few minutes after the last
request, and incoming requests don't start it again. `robots.txt` also tells search engines to stay away.
While stopped it costs only its disk, a few cents a month.

How to use it:

```sh
# start it (deploys start it too)
fly machine start $(fly machine list -a directus-cantica-test -q) -a directus-cantica-test
# … use https://test.directuscantica.cz; it stops again by itself when idle
```

Typical uses:

- **Try a code branch:** GitHub → Actions → *Deploy test instance* → *Run workflow* → pick the branch. Tick
  *load curation* if the branch also changes `curation.yaml`.
- **Try rule changes without touching production:** first get production's data onto test (below), then edit
  in the **test** admin and check the pages. When you're happy, either make the same edits in the production
  admin, or bring them over through git (export from test → commit → `curation_import` on production; see 7.6).
- **Get production's data onto test:** GitHub → Actions → *Copy production data to test* → *Run workflow*.
  This reads production without changing it (it doesn't count as an export) and replaces the curated data on
  test. Admin users and the calendar are not copied: the calendar comes from git, and test has its own admin
  user.

The two databases are separate on purpose. Nothing syncs them automatically; you copy when you need to.

### 6.3 Production

One machine in Amsterdam (`ams`), always on, with SQLite on a 1 GB volume. Fly keeps daily volume snapshots
for 5 days. On every start `bin/start.sh` runs:

1. `migrate`,
2. `calendar_build` (only if `data/` changed; on failure it keeps the old calendar),
3. `curation_import --if-empty` (only for a brand-new database),
4. gunicorn with 2 workers.

## 7. Everyday recipes

### 7.1 Change a rule or a song

Admin → *Pravidla* (or *Písně*) → edit → save. The site shows the change on the next page load. Check the
dates linked in the rule's preview. The change reaches git with the next weekly export PR, or run the export
by hand (7.4).

### 7.2 Add a rule

Admin → *Pravidla* → *Přidat*. Set the scope (for example *slavení*), the parts, the songs and the page.
Keep *pořadí* (position) close to the page number × 100, so the YAML stays sorted by page (rules for p. 41
are around 4100). The form rejects unknown songs, groups and celebration keys.

### 7.3 Review the monthly calendar PR

GitHub opens *Calendar sync* on the 2nd of each month.

- If it only adds JSON files: merge.
- If it adds celebrations to `celebrations.yaml`: read the "possible duplicate" hints in the PR. If a new
  title is a variant of an existing celebration (renamed, a diocesan form), move the title into the existing
  entry's `aliases` and delete the new entry. Otherwise keep it, check its `categories`, and set
  `categories_reviewed: true`.
- Merge. The push to `main` deploys, and the calendar is rebuilt on start.

### 7.4 Review the weekly export PR

GitHub opens *Curation export* on Mondays when the production admin has changed. The diff shows exactly what
you edited that week. Merge it: that's your backup. To export right away: Actions → *Curation export* → *Run
workflow*.

### 7.5 Get production data onto test

Actions → *Copy production data to test*. See 6.2.

### 7.6 Hand-edit the YAML and push it to production

Only for bulk edits that are easier in a text editor.

1. Make sure production has nothing unexported: run the export workflow and merge its PR first.
2. Edit `data/curated/curation.yaml` and bump `version:` at the top by one.
3. Check: `python manage.py rules_lint --file` and `python manage.py test tests`.
4. Commit and push to `main`. This deploys, but **does not** import (the database isn't empty).
5. Import: `fly ssh console -a directus-cantica -C "gosu appuser python /app/manage.py curation_import"`.

### 7.7 Review celebration categories

```sh
python manage.py calendar_catalog --review-categories > /tmp/categories.md
```

Edit `data/liturgy/celebrations.yaml`, set `categories_reviewed: true`, then run the tests and commit.

### 7.8 Add a period (named date range)

Add it to `data/liturgy/periods.yaml` (kinds: `fixed` MM-DD range, `easter` offsets, `season_week`), commit,
deploy, then use its key in a rule's *období*.

## 8. Releasing code

```sh
ruff check .
python manage.py makemigrations --check --dry-run
python manage.py test tests
git push origin <branch>            # CI runs on every branch
# optional: Actions → Deploy test instance → <branch>
git checkout main && git merge --ff-only <branch> && git push   # → CI → deploy to production
```

- The deploy restarts the machine: a few seconds of downtime.
- Migrations run on start. Make them backwards-safe: no column renames in the same release that uses them.
- If a release brings a new `curation.yaml` (for example new rules from a transcription), import it after
  the deploy, as in 7.6 step 5.

## 9. Automatic jobs (GitHub Actions)

| Workflow | When | What | If it fails |
|---|---|---|---|
| **CI** | every push / PR | ruff, migrations check, all tests | fix before merging |
| **Fly Deploy** | push to `main` | CI, then `fly deploy` to production | read the log; the old machine keeps running if the deploy fails |
| **Deploy test instance** | manual | CI, deploy a branch to test, optionally load its `curation.yaml` | — |
| **Copy production data to test** | manual | production curated data → test | test machine missing or token expired |
| **Calendar sync** | 2nd of the month | calapi → PR with new JSON files / celebrations | calapi down: run it again later. Months already fetched are kept. |
| **Curation export** | Mondays | production DB → PR with `curation.yaml`, then marks production as exported | usually an expired `FLY_API_TOKEN` |
| **Health check** | daily | `GET /health` must say `ok` | `warn` = less than 180 days of calendar left: merge a calendar PR, or run *Calendar sync* by hand |

GitHub secrets: `FLY_API_TOKEN` (deploy token for `directus-cantica`), `FLY_API_TOKEN_TEST` (for
`directus-cantica-test`). Create new ones with `fly tokens create deploy -a <app>` if they expire.

## 10. Fly.io operations

Always run management commands **as `appuser`**. Files created by root would make the database read-only for
the app.

```sh
fly status -a directus-cantica
fly logs -a directus-cantica
fly ssh console -a directus-cantica                                            # a shell (root)
fly ssh console -a directus-cantica -C "gosu appuser python /app/manage.py <command>"
fly ssh console --pty -a directus-cantica -C "gosu appuser python /app/manage.py createsuperuser"
fly machine restart $(fly machine list -a directus-cantica -q) -a directus-cantica
fly secrets list -a directus-cantica
fly certs list -a directus-cantica
```

### 10.1 Backup and restore

- **Automatic:** Fly volume snapshots, daily, kept 5 days (`fly volumes snapshots list <volume_id>`).
  The weekly `curation.yaml` export in git is a second, readable backup.
- **Manual copy of the whole database:**
  ```sh
  fly ssh console -a directus-cantica -C "gosu appuser python /app/manage.py curation_export --print --no-mark" > backup.yaml   # curated data only
  fly ssh sftp get /data/cantica.sqlite3 ./cantica.sqlite3 -a directus-cantica                                                  # whole DB
  ```
  The database runs in WAL mode, so the copied file can miss the last few writes. For curated data, prefer the
  YAML export.
- **Restore curated data** from git: `curation_import --force` (as appuser).
- **Restore everything** from a snapshot: `fly volumes create cantica_data --snapshot-id <id> -r ams -a directus-cantica`,
  then point the machine at the new volume (or clone the machine with `--attach-volume`).
- **Worst case** (volume lost): create an empty volume and deploy. The app rebuilds the calendar and imports
  `curation.yaml`, so you lose only the edits made since the last export. Then run `createsuperuser`.

### 10.2 Costs (as of 2026)

| Item | Production | Test |
|---|---|---|
| Machine shared-cpu-1x, 512 MB in `ams` | about $3.8/month (always on) | only while started |
| Volume 1 GB (the minimum) | $0.15/month | $0.15/month |
| Snapshots | free (under 10 GB) | free |
| Certificates | free (first 10) | free |

### 10.3 Region and volume

Both apps run in `ams` (cheaper than `fra`). A volume can't move between regions. To move, see "Moving an app
to another region" in the README.

## 11. Troubleshooting

| Symptom | Likely cause → fix |
|---|---|
| Page says "Pro tento den zatím nemáme liturgický kalendář" | The date is outside the data window (see `/health`) → calendar sync PR. Or `calendar_build` failed on start → `fly logs`, look for `WARNING: calendar_build failed`, fix the data in git. |
| A rule doesn't show where expected | Open the rule in the admin: does the preview list that date? If not: wrong celebration key, cycle, diocese, or min rank. If it does: a more specific rule wins (tiers), an avoid rule removes the song, or the rule is *jen bez vlastní písně*. Turn on *zobrazit zdroje* to see why each song is there. |
| A song from a `#section` is missing k přijímání / na závěr | Its verse field is empty (not verified) → fill it in under Písně. |
| `curation_import` says "the DB has changes that were never exported" | Export first (*Curation export* workflow, merge the PR) or add `--force` if you really want to discard them. |
| Admin "attempt to write a readonly database" | A command ran as root and created a root-owned file → `fly ssh console -C "chown -R appuser:appuser /data"`, then always use `gosu appuser`. |
| Old styling after a deploy | Shouldn't happen (pages always revalidate). Hard-reload the browser, then check that the deploy succeeded. |
| Test site doesn't load | It's stopped by design → `fly machine start …` (6.2). |
| Health check `warn` | Less than 180 days of calendar left → merge the calendar PR or run *Calendar sync*. |

## 12. Reference

### 12.1 Management commands

| Command | What it does | Touches DB |
|---|---|---|
| `calendar_sync [--start YYYY-MM] [--end YYYY-MM] [--calendar …]` | fetch months from calapi into `data/calendar/raw/` | no |
| `calendar_catalog [--register-new]` | check that every title has a catalog key; add new ones | no |
| `calendar_catalog --review-categories` / `--suggest-categories` | category review listing / fill in guesses | no |
| `calendar_build [--check] [--force]` | validate `data/` and rebuild the calendar tables | yes |
| `curation_export [--path F] [--print] [--no-mark] [--mark-exported V]` | DB → YAML | marks exported |
| `curation_import [--path F] [--if-empty] [--force]` | YAML → DB (replaces songs, groups, rules) | yes |
| `rules_lint [--file] [--coverage]` | check the ruleset against the calendar | no |

### 12.2 URLs

| URL | |
|---|---|
| `/`, `/2026-12-24/` | day page (`?dieceze=olm` picks a calendar and remembers it in a cookie) |
| `/prilezitosti/`, `/prilezitosti/pohreb/` | sacraments and other services (Direktář pp. 47–48) |
| `/o-aplikaci/` | about |
| `/api/v1/days/2026-12-24.json?dieceze=olm` | JSON (unstable until v2.1) |
| `/admin/` | admin |
| `/health` | calendar freshness (JSON, used by the daily check) |
| `/live` | Fly's liveness check |
| `/robots.txt` | test: disallow everything; production: everything except admin and API |

### 12.3 Environment variables

| Variable | Meaning |
|---|---|
| `CANTICA_ENV` | `production` on Fly (manifest static files, secure cookies) |
| `DEBUG` | `1` locally; never on Fly |
| `SECRET_KEY` | Fly secret |
| `ALLOWED_HOSTS` | in the toml files |
| `DATABASE_PATH` | `/data/cantica.sqlite3` on Fly |
| `CANTICA_NOINDEX` | `1` on test: robots.txt disallows everything |
| `UMAMI_WEBSITE_ID`, `SENTRY_DSN` | optional analytics and error tracking |
