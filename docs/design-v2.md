# Directus Cantica v2 — design

Status: **draft for review** · 2026-10-30

This document describes a rebuild of Directus Cantica. It is meant to be argued with: every decision below is open unless it follows directly from the principles in §1. Open questions are collected in §14.

---

## 0. Summary

- **Fresh start**, same repo (branch `v2`), same stack (Django 5.2 LTS + admin), same look. No code, rules or data migrate from v1 (one optional exception, §6.4).
- **Honesty is the product.** Every recommendation points to a rule, and every rule to a source: a page of *Direktář pro varhaníky*, or explicitly "doporučení autora". Each mass part says how specific our knowledge is (▲ ■ ●), or that we have none.
- **Deterministic.** Same date + diocese + ruleset version → same output. No randomness when a page is served.
- **Calendar as committed data.** calapi is used by an importer, not by the website. Raw responses are stored in git and the DB is built from them.
- **Rules in the DB, edited in the admin, exported to YAML in git.** Tests and lint run against the YAML.
- **Pure-Python engine** with no ORM inside. It is fast enough to compute any day in microseconds.
- **Dioceses.** A diocese selector controls the calendar. Songs are a single list, as on kancional.cz.
- **Detailní doporučení is a core feature.** For each mass we show one valid combination of songs, part by part, each with its reason and the other options. The choice is deterministic but varies from week to week, which is how the app promotes non-trivial combinations.
- **Fast navigation.** The first load is server-rendered; switching days fetches an HTML fragment, with neighbouring days prefetched.

---

## 1. Goals, principles, non-goals

**Value over pisnekemsi.cz:** correctness and reliability. Where they estimate, we cite. Where we don't know, we say so.

| # | Principle | Consequence |
|---|---|---|
| P1 | Traceability | Every candidate carries `reasons[]` → rule → source (page or author). |
| P2 | No false certainty | Each mass part has a coverage state: ▲ / ■ / ● / *nic*. A gap is shown in the UI, not filled in. |
| P3 | Determinism | No `random`, no `order_by('?')`. Ties are broken by source order. |
| P4 | Data is versioned | Calendar snapshots, rules and catalog live in git, are reviewed in PRs and are tested. |
| P5 | No runtime dependencies | The website never calls calapi or kancional.cz. |
| P6 | Suggestion, not command | We show *options with reasons*; the organist (and the priest) decide. |

**Non-goals for v2:** Mešní zpěvy, accompaniment links, matching songs to readings, any AI/LLM, user accounts (other than the admin), the responsorial psalm table (planned later, §12).

---

## 2. Rewrite or refactor? → Rewrite

Reasons:
- Nearly every v1 model changes. That includes `Song.number`, which is an int and has 16 collisions; the generic-FK rules; and celebration identity, which is derived from API title slugs.
- v1 has no tests, no users, and a ruleset you don't trust. Nothing needs preserving or comparing against.
- The code worth keeping is small: the template and CSS, the calapi client idea, and the ▲■● tiers.

**Kept:** visual design (template + CSS), Django + admin, Fly.io, the three-tier concept, the domain names.
**Dropped:** all models and migrations, all rules, committed `staticfiles/` and `static/`, `prod20251124.dump` (purged from history, §11), the debug and preload endpoints, DRF (§9.4).

Process: create branch `v2`, delete the old apps, build the new layout (§4). When M5 is done, it replaces `main`.

---

## 3. Vocabulary

**Mass parts** (`MassPart` is a DB table, so new parts can be added as data; listed in display order):

| code | label | note |
|---|---|---|
| `before_mass` | před mší | e.g. 101 / 128 in Advent |
| `mass` | mešní píseň | a song used through the mass (entrance, gospel, offertory, maybe more) |
| `entrance` | ke vstupu | |
| `asperges` | kropení | 510, 511 |
| `sequence` | sekvence | 406, 422, 717 |
| `gospel` | před evangeliem | |
| `offertory` | k obětnímu průvodu | |
| `communion` | k přijímání | **includes díkůvzdání** (your practice; M5 is not a separate part) |
| `recessional` | na závěr | convention, not part of the mass |
| `after_mass` | po mši | e.g. 811 at Lourdes, 922/924 2.–8. 11., 912/913 around sv. Marek |
| `ashes`, `procession`, `veneration`, `transfer`, `adoration`, `baptismal_water`, `litany` | special rites | Ash Wednesday, Hromnice, Palm Sunday, Holy Week, Corpus Christi, Easter Vigil |

**Tiers (specificity),** taken from the scope of the matching rule (§7.2):
- ▲ **podle svátku**: a rule for this celebration
- ■ **podle typu svátku**: a rule for a category (apoštolové, mučedníci, Panna Maria…)
- ● **podle období**: a rule for a period, season or the whole year
- *nic*: no rule says anything about this part

**Strength:** `prescribed` (předepsáno / vždy), `recommended`, `alternative` (the book's parentheses, "též", "možno"), `avoid` (nehrajeme / není vhodná).

**Source:** `direktar` + page number, or `author` (your own convention, labelled as such in the UI).

---

## 4. Architecture

```
          (GitHub Action, monthly)                     (one-time + manual)
calapi ──► calendar_sync ──► data/calendar/raw/*.json   kancional.cz ──► catalog_import ──► data/catalog/songs.yaml
                                     │ (git, PR)                                                 │
                                     ▼                                                           ▼
                              calendar_build ─────────────────► DB ◄──────────── catalog_load ───┘
                                                                ▲ │
                                     admin (rules, songs,       │ │ rules_export (Action, weekly PR)
                                     groups, celebrations) ─────┘ ▼
                                                        data/rules/*.yaml ──► CI: tests, lint, snapshots
request (date, diocese)
   └► DayContext (from DB)  +  Snapshot (rules/catalog, in memory, keyed by ruleset_version)
         └► engine.recommend() → DayResult ─► HTML page / HTML fragment / JSON
```

Repository layout:

```
cantica/        settings, urls
liturgy/        Diocese, CalendarDay, Occurrence, Celebration(+Alias), Category, Period;
                calendar_sync / calendar_build commands; norms.py (Gloria/Credo/Aleluja, cycles)
catalog/        Song, SongGroup; catalog_import / catalog_load
rules/          Rule, RuleTarget, admin, YAML import/export, lint, coverage report, snapshot adapter
engine/         PURE PYTHON — types.py, context.py, match.py, resolve.py  (no django imports; enforced by a test)
web/            views, templates, static (css/js), JSON API
data/           calendar/raw/, catalog/, rules/   (committed)
tests/          unit/, book/ (assertions from Direktář), snapshots/
docs/
```

---

## 5. Liturgical calendar

### 5.1 Source: calapi (`calapi.inadiutorium.cz`)

Facts verified on 2026-10-30:
- Calendars: `czech`, `czech-cechy`, `czech-morava`, `czech-pha`, `czech-ltm`, `czech-hk`, `czech-cb`, `czech-plz`, `czech-olm`, `czech-brn`, `czech-oo`.
- A day returns `{date, season, season_week, weekday, celebrations[{title, colour, rank, rank_num}]}`.
- **No stable id** for celebrations. Titles can differ between calendars for the same feast (Cyril a Metoděj: "…patronů Evropy, hlavních patronů Moravy").
- Rank labels: `slavnost`, `svátek`, `památka`, `nezávazná památka`, `připomínka`, `ferie`, `Primární liturgické dny`. `rank_num` follows the Table of Liturgical Days (1.1 … 4.0).
- There is no `triduum` season: Velký pátek and Bílá sobota come back as `lent`.
- `GET …/{year}` returns `{lectionary, ferial_lectionary}` for the liturgical year that **begins in Advent** of `{year}`. This is a known off-by-one trap.
- HTTP only, and it is a volunteer-run service: treat it as unreliable.

### 5.2 Sync pipeline

- **`calendar_sync --from YYYY-MM --to YYYY-MM [--calendar …]`**
  - Fetches month by month, with a 10 s timeout and 3 retries with exponential backoff.
  - Writes `data/calendar/raw/{calendar}/{yyyy-mm}.json` with stable formatting, so that git diffs show real changes.
  - Idempotent; it never touches the DB.
- **`calendar_build`**: raw JSON → DB, in one transaction. Validation (fails loudly and lists every problem):
  - every date in the range is present, for every calendar;
  - every day has at least one celebration and a season from the known set;
  - **every non-`ferie` title maps to a known `Celebration`** (directly or via an alias). Unknown titles fail the build, so a new feast or a renamed title is caught instead of silently producing a rule-less celebration.
- **`calendar_catalog [--register-new]`** (no DB): checks that every non-`ferie` title is in `data/liturgy/celebrations.yaml`; with `--register-new` it adds unknown titles and prints possible duplicates.
- **GitHub Action (monthly):** syncs the window [today − 1 month, today + 24 months], registers new titles, validates with `calendar_build --check` and opens a PR. Merging redeploys; the container start script (`bin/start.sh`) runs `migrate && calendar_build`. *(Changed in M1: not Fly's `release_command`, because the release machine does not mount the SQLite volume.)*
- **Health:** `/health` reports the last date covered; the Action fails (and emails you) if fewer than 180 days remain.

Effort: 11 calendars × 12 months = 132 requests per year of data.

### 5.3 Model

```
Diocese(code PK 'pha', name, calapi_calendar 'czech-pha')     + a "Česká republika (obecný)" entry → 'czech'
Category(key PK, name)          lord, virgin_mary, apostle_evangelist, martyr, pastor, doctor, virgin,
                                religious, saint, czech_patron, angel, dedication, dead
Celebration(key PK slug, name, categories M2M Category, categories_reviewed bool)
CelebrationAlias(title, celebration FK)
CalendarDay(diocese FK, date, season, season_week, sunday_cycle 'A|B|C', ferial_cycle 1|2)   unique(diocese, date)
Occurrence(day FK, celebration FK NULL, title, rank_label, rank_num, colour, position)
CalendarBuild(built_at, source_digest, first_date, last_date, days)
Period(key PK, name, kind, params JSON, description)      §5.5 — added in M3, together with the rules
```

**Changed in M1: the celebration catalog lives in git, not in the admin.** `data/liturgy/celebrations.yaml` (key, name, aliases, categories, categories_reviewed) is the source of truth, and the DB mirrors it on every `calendar_build`; the calendar admin is read-only. Reasons:
- celebration identity belongs with the calendar snapshots it describes, and new titles arrive through the calendar-sync PR, where CI can validate everything without a prod DB;
- no two-way sync between the DB and YAML for the calendar side;
- reviewing ~500 categories is faster in one YAML file than in admin forms.

Rules (M3) stay in the DB + admin, as decided; they reference celebrations by key.

- **Celebration identity:**
  - Every occurrence whose rank is not `ferie` becomes a `Celebration` with a key that never changes once created (e.g. `sv-prokopa-opata`, `4-nedele-adventni`).
  - Plain ferias are described by season, week and weekday and are not catalogued.
  - Rank is stored per **occurrence**, because it differs by diocese (sv. Prokop is a memorial in Bohemia and optional in Moravia).
- **Categories** drive the ■ tier, so they are curated in the YAML (M4). The first assignment comes from a title-keyword heuristic and is marked `categories_reviewed: false`.
- **Which occurrences are mass options:**
  - Every occurrence except a `připomínka`. A feria and an optional memorial on the same day are two options.
  - A `připomínka` is shown as a note under the main option.
  - Options are ordered by `rank_num`.

### 5.4 Cycles and norms (code, unit-tested)

- `sunday_cycle` = `"ABC"[(Y − 1) % 3]` and `ferial_cycle` = `2 if Y % 2 == 0 else 1`, where Y is the calendar year in which the liturgical year **ends**. Cross-checked against calapi `/{year}` in a test.
- `norms.py` decides **Sláva na výsostech**, **Věřím** and **Aleluja / Chvála tobě, Kriste** from rank, season and period:
  - Gloria: Sundays outside Advent and Lent, solemnities, feasts, the Christmas and Easter octaves, Holy Thursday.
  - Credo: Sundays and solemnities.
  - No Aleluja in Lent.

  These are general norms, so they live in code, not in rules. They are shown as badges.

### 5.5 Periods (data, not code)

Periods are named date ranges that rules can target. A period's `kind` decides how its dates are computed:

| kind | params | examples (book page) |
|---|---|---|
| `fixed` | from MM-DD, to MM-DD | `advent_late` 12-17..12-24 (17), `christmas_octave` 12-25..01-01 (19), `unity_week` 01-18..01-25 (30), `may` 05-01..05-31 (34), `all_souls_week` 11-02..11-08 (44) |
| `easter_offset` | from, to (days relative to Easter) | `holy_week` −7..−1, `triduum` −3..−1, `easter_octave` 0..7 (24), `pentecost_novena` 40..48 (24), `before_ascension` 0..38 (24, for "415 zásadně nezpíváme") |
| `season_week` | season, weeks | `ordinary_34` (26, 44), `lent_5plus` (19–20) |
| `season_part` | season, from-date rule | `advent_early` (1st Sunday of Advent .. 12-16) (17) |

### 5.6 Later (not v2)

Computing the calendar locally (algorithmic temporale + sanctorale data files per diocese), with calapi kept only as a test oracle over 2020–2040. The raw-snapshot design makes this an easy swap.

---

## 6. Song catalog

### 6.1 Model

```
Song(code PK '708A' | 'Z781' | '523', number '708' (derived), position (derived, Kancionál order),
     title, section,
     mass_song      bool | NULL,       # can serve as "mešní píseň"
     communion_verses   str | NULL,    # see below
     recessional_verses str | NULL,    # same semantics
     verse_count int | NULL,           # optional; enables the "verse > count" check
     reviewed bool, note)
SongGroup(key PK, name, description, source_page, songs: ordered M2M Song through SongGroupMember)
CurationState(version, exported_version)   # single row; §7.6
```

- **One list of songs, exactly as on kancional.cz.** There is no edition model: organists look songs up there or in their printed copy with all the appendices.
- **Codes come from kancional.cz:** letter suffixes (`101A/B/C`, `813A/B`) and the `Z` prefix for appendix songs. The current integer field cannot represent them.
- **A rule can target a number or an exact code.** A number (`"813"`) expands to its letter variants (`813A`, `813B`) but **not** to the `Z` song with the same number (`781` ≠ `Z781`). An exact code (`"813B"`, `"Z781"`) targets only that song.
- **The book's OL/HK footnotes** ("OL též 892") become `alternative` rules pointing to the matching kancional.cz code, which is identified by title during transcription. They carry the public note "olomoucká / královéhradecká verze Kancionálu".
- **M-markers are not trusted** (your point). Instead, two curated fields record verse suitability:

  | value | meaning | shown to users |
  |---|---|---|
  | `NULL` | not verified | nothing |
  | `'-'` | the song has no suitable verse | nothing |
  | `'*'` | yes, use the verse dedicated in Kancionál | nothing (Kancionál says it already) |
  | `'4'`, `'4,5'` | these specific verses | **yes**: "k přijímání 4. sl." (useful for songs without printed dedications) |

  The engine never treats `NULL` as yes. "Not verified" is an admin-only state and never reaches the UI (§8.2).
  *(Changed in M2: "none" is `-`, not the empty string, because the admin saves an empty field as NULL.)*
- **Groups make "512 ad." explicit.** `mesni_obecne` = 512–525, 588–593, Z582 (membership curated). The book's lists become groups: `k_panu_jezisi_mesni` (702, 707, 708, 709, 710, 711, 715, 717, 728), `prilezitostne_mesni` (904, 911, 917, 918), `advent_k_prijimani` (106–108, 114–116, 127), `postni_kajicne` (322, 321, 320, 319, 312, 309), `marianske` (801–820), …
- **No song texts are stored**: only codes, titles, sections and your annotations. Links go to kancional.cz.

### 6.2 Import — done once, no scraper *(changed in M2)*

The catalog is static, so instead of a scraper the numbered list from `kancional.cz/ciselny-seznam` was transcribed once (2026-10-30; 511 entries in 14 sections, including prayers, ordinaria and psalm responses, since rules refer to e.g. 681, 682, 696). The result is `data/curated/curation.yaml`, one line per song, together with the first 15 groups from the book (pp. 8, 9, 17, 18, 20, 25, 27, 48). Verse counts and the printed M-markers are not imported: the markers are untrusted anyway, and `verse_count` can be filled in where needed.

**One curation file for everything edited in the admin** (songs and groups now, rules in M3): `data/curated/curation.yaml`. `curation_export` writes it, `curation_import` loads it; the start script imports it only into an empty DB.

### 6.3 Curation UI

The Song admin list has inline-editable `mass_song`, `communion_verses`, `recessional_verses`, `verse_count` and `reviewed`, filters by section, review state and each verse state (neověřeno / nemá / podle Kancionálu / konkrétní sloky), and a link to the song on kancional.cz. Groups are edited with an ordered inline list of songs (autocomplete).

### 6.4 Optional seed from v1

**Decided: prefill.** v1 `has_communion_verse` / `has_recessional_verse` (326 songs) are matched to kancional.cz codes by (number, title), because v1 numbers collide.
- `True` → `'*'`.
- `False` → `NULL`. v1 cannot tell an explicit "no" from an untouched default, so we don't claim "none".
- All prefilled songs start with `reviewed: false`, so they appear in the admin's "not reviewed" filter.
- **Also pre-set (M2 review): `mass_song = true`** for the members of `mesni_obecne`, `k_panu_jezisi_mesni`, `prilezitostne_mesni` and every song v1 used as the main mass song (131 songs), unreviewed.
- Result: 324 of 326 v1 songs matched automatically, the two v1 typos (895, Z781) by hand; 171 songs have a communion verse `*`, 215 a recessional verse `*`.

---

## 7. Rules

### 7.1 Shape

A rule is roughly **one clause of the book**.

```
Rule
  scope            celebration | category | period | season | occasion | global     (exactly one target FK / value)
  celebration FK?, category FK?, period FK?, season?, occasion FK?
  filters (all optional, ANDed):
    season              e.g. category=martyr + season=easter
    sunday_cycles       subset of {A,B,C}
    day_kind            any | sunday | weekday
    min_rank            e.g. only memorials and higher
    dioceses M2M        empty = all
  parts M2M MassPart    ≥ 1
  strength              prescribed | recommended | alternative | avoid
  action               songs | neighbours | note
    songs:      ordered RuleTarget(song FK | group FK, verses str?, include_variants bool=true)
    neighbours: window_days (default 7), min_rank (default memorial)
    note:       text only (e.g. "Varhany mlčí", "Při vstupu a na závěr se nic nezpívá")
  public_note           shown to users (e.g. "není vhodná 817 – je to slavnost Pána Ježíše")
  internal_note
  source                direktar | author
  source_page int?      required when source=direktar
  position int          order within the source (used to break ties)
  active bool
```

Rules use explicit columns and FKs (no generic FK, no free JSON): the admin gets dropdowns and filters, and the DB enforces integrity. A check constraint requires exactly one scope target.

### 7.2 Scope → tier → specificity

| scope | tier | specificity |
|---|---|---|
| celebration | ▲ | 5 |
| category | ■ | 4 |
| period | ● | 3 |
| season | ● | 2 |
| global | ● | 1 |
| occasion | (own page) | — |

Filters narrow when a rule applies; they never change its tier.

### 7.3 Resolution (per mass option, per part)

1. **Match:** a rule applies if its scope and filters hold for the day, the mass option and the diocese.
2. **Expand:** groups and numbers become song codes. The group identity is kept for display.
3. **Avoid filter:** a candidate is removed if an `avoid` rule hits the same song at **≥** its specificity.
   - This makes "no Marian songs at mass in May" (period, 3) give way to Marian celebrations (▲ 5 / ■ 4), exactly as the book says ("Vyjma mší o Panně Marii…", p. 34).
4. **Merge:** a song recommended by several rules keeps its best (strength, specificity), and all reasons are collected.
5. **Order:** by strength (prescribed > recommended > alternative), then specificity, then `position`.
6. **Coverage:** the tier of the best candidate, or *nic*.

**Several songs for the same part are normal.** For example, 828 and 829 can both be sung through the mass on sv. Cyril a Metoděj. All of them are listed, and the detailní doporučení may use more than one of them (§8.3). The only real contradiction is a song being both recommended and avoided at the **same** specificity for the same part and day. Lint reports that as an error (§7.6); at runtime, `avoid` wins.

### 7.4 Neighbour rules (the book, p. 27)

> "Na závěr zpíváme píseň aktuálně ze slavnosti, svátku či památky z předešlého či následujícího týdne…"

This is a rule with `action=neighbours`:
1. It collects celebrations within ±`window_days` with rank ≥ `min_rank`.
2. It takes their ▲ `mass` candidates and offers them for `recessional`.
3. The reason reads "ze svátku sv. Cyrila a Metoděje (ne 5. 7.)".
4. The candidates' tier is the rule's own (●), and neighbour rules never chain.

### 7.5 Examples (transcribed from the book)

```yaml
- scope: {celebration: sv-prokopa-opata}            # Kalendárium, červenec, p. 38
  parts: [entrance]
  strength: recommended
  songs: [{song: "838", verses: "5"}]
  source: {direktar: 38}

- scope: {celebration: sv-cyrila-a-metodeje}
  parts: [mass]
  strength: recommended
  songs: [{song: "828"}, {song: "829"}]
  source: {direktar: 38}
- scope: {celebration: sv-cyrila-a-metodeje}
  parts: [entrance]
  strength: recommended
  songs: [{song: "838", verses: "1"}]
  source: {direktar: 38}

- scope: {category: apostle_evangelist}             # p. 8
  parts: [mass]
  strength: recommended
  songs: [{song: "827"}]
  source: {direktar: 8}

- scope: {period: unity_week}                       # p. 30: "na závěr vždy 910"
  parts: [recessional]
  strength: prescribed
  songs: [{song: "910"}]
  source: {direktar: 30}

- scope: {period: may}                              # p. 34
  parts: [mass, entrance, gospel, offertory, communion]
  strength: avoid
  songs: [{group: marianske}]
  public_note: "Mariánské písně se mohou hrát po mši nebo při májových pobožnostech."
  source: {direktar: 34}

- scope: {celebration: zvestovani-pane}             # p. 32
  parts: [mass]
  strength: avoid
  songs: [{song: "817"}]
  public_note: "Není vhodná – je to slavnost Pána Ježíše, ne Panny Marie."
  source: {direktar: 32}

- scope: {celebration: 5-nedele-v-mezidobi}         # p. 26: "5.C – povolání apoštolů: 827"
  filters: {sunday_cycles: [C]}
  parts: [mass]
  strength: recommended
  songs: [{song: "827"}]
  source: {direktar: 26}

- scope: {season: advent}                           # your convention, not the book
  parts: [mass, entrance, gospel, offertory, communion]
  strength: avoid
  songs: [{group: marianske}, {group: svatym}, {group: prilezitostne}]
  source: author
  internal_note: "Overridden by ▲/■ rules (e.g. 8. 12.)."
```

### 7.6 Authoring, versioning, lint

- **Source of truth is the DB** (your choice). Rules join songs and groups in the single curation file `data/curated/curation.yaml` (built in M2): `curation_export` writes it, a weekly Action exports production and opens a PR with the diff, `curation_import` loads it (initial transcription, bulk edits).
- **Overwrite guard (built in M2):** `CurationState` holds `version` (bumped on any save or delete of curated data) and `exported_version`. Import refuses if the DB has changes that were never exported, unless `--force` is given; importing identical content is a no-op.
- **The engine snapshot and the caches are keyed by** (`CurationState.version`, latest `CalendarBuild`). Celebrations and periods are calendar-side data (git), so a calendar rebuild also invalidates the caches.
- **Admin rule preview:** "this rule applies on: …" (next 24 months, per diocese), so a mistyped scope is visible right away.
- **Lint** (in the admin and in CI) over 3 years × all dioceses:
  - errors: a song both recommended and avoided at the same specificity for the same part and day; unknown song codes; a `mass` part targeting a song with `mass_song = false`; a `direktar` source without a page;
  - warnings: verse number > `verse_count`; rules that never fire.
- **Coverage report** (admin): upcoming celebrations of rank ≥ memorial whose `mass` part is ● or *nic*. This is your authoring to-do list, and it shows exactly where we say "nevíme".

---

## 8. Engine

### 8.1 Contract

```python
def recommend(ctx: DayContext, snap: Snapshot) -> DayResult  # pure, no I/O, no Django
```

- `DayContext`: date, diocese, season, season_week, weekday, cycles, active periods, occurrences (with celebration key, categories, rank, colour), and neighbour occurrences ±7 days.
- `Snapshot`: immutable rules, songs, groups and periods plus `version`; built once per process per version.
- `DayResult`:

```
DayResult(date, diocese, season, week, cycles, norms{gloria, credo, alleluia}, ruleset_version, calendar_source,
          masses: [MassResult])
MassResult(occurrence{title, rank_label, colour}, commemorations[], notes[],
           parts: [PartResult(part, coverage: '▲'|'■'|'●'|None, candidates[Candidate], notes[])],
           plan: Plan)
Candidate(song|group, verses?, strength, tier, excluded[], reasons[Reason(rule_id, source, page, text)])
Plan([PlanEntry(part, songs[(code, verses?)], tier, reasons[], alternatives_count)])
```

### 8.2 Verse hints

A mass song's curated verse fields decide two things:
1. whether the plan may use the mass song for communion or the závěr (`'*'` or specific verses: yes; `''` or `NULL`: no, and the plan picks a separate song);
2. whether the UI shows a verse hint. Only specific verse numbers are shown ("k přijímání 4. sl."). `'*'`, `''` and `NULL` show nothing.

So "unverified" never reaches the user. It only makes the plan conservative: adding a separate communion song is always valid.

### 8.3 Detailní doporučení (the plan)

For each mass option we build **one** combination, part by part, using only the candidates from §7.3. This is what v1's "detailní doporučení" showed; v2 makes it principled.

**Algorithm:**
1. **Mešní píseň.** Take the best class of `mass` candidates (same strength and specificity). If it contains several **prescribed** songs, the plan uses all of them (828, 829). Otherwise it picks one (see *Variety* below).
2. **Vstup, před evangeliem, obětní průvod** are covered by the mass song. The exception: a candidate for that part with a **higher tier** than the mass song, or a **prescribed** one, replaces it for that part. Example: Prokop → "ke vstupu 838/5, dále mešní píseň" (p. 9).
3. **Přijímání:**
   - a prescribed or higher-tier communion candidate is used first;
   - otherwise, if the mass song has a communion verse (`'*'` / verses), *Variety* decides between that verse and a separate communion candidate (e.g. a 700 song). Both are valid, and alternating them is how the app promotes non-trivial combinations;
   - otherwise a separate communion candidate is used.
4. **Závěr:** prescribed or ▲/■ candidates first; then neighbour candidates (§7.4), if any; then *Variety* between the mass song's závěr verse (if any) and ● candidates.
5. **Special parts** (kropení, sekvence, popelec, průvod, …) appear only when they have a candidate.
6. **No duplicates:** a song appears only once in the plan, except the mass song across the parts it covers.
7. **Gaps stay visible:** a part with no candidate shows "—" and "Direktář neuvádí".

**Variety:**
- Ties are broken by a deterministic seed: (liturgical year, week, weekday, occurrence key, diocese). Reloading gives the same result; next week usually gives a different valid combination.
- The mass song chosen for the same weekday one week earlier is skipped when an alternative exists. That plan is computed without this step, so there is no recursion.

**Each plan entry shows:**
- the song (with a verse hint, if any);
- its tier symbol and reason ("Direktář s. 38", "obecné doporučení pro mezidobí", "doporučení autora");
- an expander "další možnosti (n)" that lists the other candidates for that part.

The section starts with one line of framing: *"Jedna z možných sestav podle Direktáře – výběr je na vás."*

### 8.4 Performance

The ruleset (hundreds of rows) is matched in memory. `DayResult` is cached per process in an LRU keyed by (date, diocese, version), and building `DayContext` takes ≤ 3 queries. Target: < 30 ms server time for an uncached day.

---

## 9. Web

### 9.1 URLs

```
/                         today (Europe/Prague, timezone-aware)
/2026-11-01/              a day          (?dieceze=olm overrides the cookie)
/2026-11-01/?fragment=1   just <main> for in-page navigation
/prilezitosti/            occasions (svatba, pohřeb, křest, biřmování, pomazání nemocných, bohoslužba slova) — p. 47–48
/o-aplikaci/
/api/v1/days/2026-11-01.json?diocese=olm
/health
/admin/
```

Invalid dates return 404, not 500. Dates outside the calendar data show a clear message, not an empty page.

### 9.2 Navigation and speed

- About 50 lines of vanilla JS: the arrows, "dnes" and the date picker fetch `?fragment=1`, swap `<main>` and `pushState`. ±3 days are prefetched in the background, so navigation feels instant. Without JS, the plain links still work.
- `Cache-Control: public, max-age=3600` and an `ETag` built from (date, diocese, ruleset_version, calendar version).
- Fly: one machine always on (no scale-to-zero cold starts).

### 9.3 UI (same look, small additions)

- **Celebrations:** ordered by rank, with a liturgical-colour stripe and a rank label (slavnost / svátek / památka / nezávazná památka).
- **Diocese selector** in the header, remembered in a cookie (§9.5).
- **Badges:** Sláva · Věřím · Aleluja / Chvála tobě, Kriste.
- **Summary (always visible):** ▲ ■ ● candidates as today. Verses are shown as "838 (5. sl.)", the part as a small label when it is not *mešní píseň*, and groups as one chip ("mešní písně obecné") that expands.
- **Detailní doporučení (hidden by default, as now):** the plan from §8.3, one row per part, each with its reason and "další možnosti".
- **Honest wording for gaps:** "Pro tuto památku Direktář žádnou konkrétní píseň neuvádí. Platí obecná doporučení pro mezidobí."
- **Saturday:** a link "Večerní mše z neděle →".
- Fix: the details panel no longer has a fixed `max-height`.

### 9.4 JSON API

The API is a plain Django `JsonResponse` serializing `DayResult`; DRF is not needed. It is documented as unstable until v2.1.

### 9.5 Privacy (no cookie banner needed)

- **The diocese cookie** is set only when the user picks a diocese. It stores only that choice, with no tracking. A preference the user explicitly asked for counts as strictly necessary under the ePrivacy rules (in Czech law, § 89 odst. 3 zákona 127/2005 Sb.), so no consent banner is required. A single sentence on the about page says what the cookie does. (I'm not a lawyer; this is the common reading for preference cookies.)
- **Umami** analytics is cookieless, so it needs no banner either.
- **Google Fonts:** self-host Fira Sans (a few WOFF2 files, served by WhiteNoise). Loading fonts from Google sends visitors' IP addresses to Google. A German court ruled that a GDPR violation (LG München, 2022), and self-hosting is also faster.
- The Buy Me a Coffee button image is downloaded once and served locally, for the same reason.

---

## 10. Testing

| layer | what | where |
|---|---|---|
| unit | periods, cycles, norms, resolution rules (§7.3) on tiny fixture rulesets | `tests/unit` |
| purity | `engine/` imports nothing from `django`, `liturgy`, `rules`… | `tests/unit/test_purity.py` |
| book assertions | ~50 hand-picked cases, each citing a page, aimed at the **tricky behaviour**: rules firing on the right date in each diocese, avoid rules giving way (May vs Marian feasts), neighbour rules, periods, cycles A/B/C, plan construction. They catch engine and scope bugs; transcription typos are caught by your review, not by tests derived from the same reading. | `tests/book/*.yaml` |
| lint | §7.6 errors fail CI | `tests/test_lint.py` |
| snapshots | `DayResult` JSON for 2 liturgical years × 3 dioceses; diffs are reviewed in PRs to catch unintended changes | `tests/snapshots/` |
| import | `calendar_build` on recorded raw files, including failure cases (missing day, unknown title) | `tests/unit` |

Book assertion format:

```yaml
- date: 2027-07-05
  diocese: czech
  mass: {celebration: sv-cyrila-a-metodeje}
  expect:
    mass:     {includes: ["828", "829"], tier: "▲"}
    entrance: {includes: ["838/1"]}
  source: 38
- date: 2027-05-12
  diocese: czech
  mass: {feria: true}
  expect:
    mass: {excludes_group: marianske}
  source: 34
```

---

## 11. Operations and security

- **Security (do first, independent of v2):**
  - purge `prod20251124.dump` from git history (`git filter-repo`, then force-push) and rotate the admin password, because the hash is public;
  - the v2 project has no debug or preload endpoints;
  - Sentry gets its DSN from an env var, runs in production only, with `send_default_pii=False`.
- **DB: SQLite on a Fly volume** (decided), in WAL mode.
  - Everything except your latest admin edits can be rebuilt from git (calendar snapshots, catalog and rules exports).
  - Fly takes daily volume snapshots, and the weekly rules-export PR covers the rest.
  - The separate Fly Postgres app is retired.
- **Fly config:**
  - fix the paths (`/app`, not `/code`);
  - `min_machines_running = 1`;
  - no `release_command` (its machine has no volume); `bin/start.sh` runs `migrate && calendar_build` (+ `catalog_load --if-changed` from M2) before gunicorn, and a failed build keeps serving the previous data;
  - Fly's health check uses `/live`; `/health` (data freshness) is for the daily monitoring Action;
  - no `[[statics]]`, because WhiteNoise serves static files;
  - `staticfiles/` is not committed.
- **CI (GitHub Actions):** ruff, tests, lint, snapshot diff; deploy on `main`.
- **Scheduled:** `calendar_sync` monthly → PR; `rules_export` weekly via `fly ssh console -C` → PR; a health check.
- **Versions:** Python 3.13, Django 5.2 LTS (supported until 04/2028).

---

## 12. Milestones

| | scope | done when |
|---|---|---|
| **M1 Foundation** ✅ code | skeleton, CI, settings, calendar sync/build, dioceses, norms, day page showing calendar only (ranked celebrations, colours, badges) | deployed to `test.directuscantica.cz` with 24 months of data |
| **M2 Catalog** ✅ code | catalog import, v1 flag prefill, groups, curation admin | every song in sections 100–900 present; groups defined for the book's lists |
| **M3 Rules + engine** | models, admin, YAML I/O, lint, engine incl. the plan (§8.3), book-assertion harness; transcription of *Obecné zásady* and *Liturgické doby* (pp. 6–28) | assertions for pp. 6–28 pass |
| **M4 Kalendárium + occasions** | transcription of pp. 29–46 (months) and 47–48 (occasions page), category review, coverage report | coverage report reviewed by you |
| **M5 Launch** | fragment navigation + prefetch, diocese selector, JSON API, self-hosted fonts, wording, about page | v2 replaces v1 on `directuscantica.cz` |
| later | responsorial psalm table (pp. 51–59), readings matching | — |

**Transcription.** The book has to become rules one way or another: roughly 200–250 clauses. A YAML file isn't an extra format: it is the same file the export (§7.6) produces, and the import exists anyway for the first load. So I draft it from the scan, one entry per clause with its page, and you review it next to the book. That replaces several hours of form-filling in the admin. The risk is a misreading of the scan; that is why every entry cites its page and you review it. I'll start once the format is final (M3), not before.

---

## 13. Risks

| risk | mitigation |
|---|---|
| calapi disappears or changes format | raw snapshots cover 24 months ahead; build validation catches format changes; local computation is the fallback (§5.6) |
| Book (≈2016) predates newer memorials | the gap is shown honestly; author rules can fill it, labelled as such |
| Transcription errors | page reference on every rule, an assertion per clause, your review |
| OL/HK footnote songs mapped to the wrong kancional.cz code | identified by title during transcription; listed separately for your review |
| Copyright | only codes, titles and our annotations are stored; no song or reading texts; links to kancional.cz |
| Scope creep | non-goals in §1; psalms and readings only after M5 |

---

## 14. Decisions (review round 1)

| # | topic | decision |
|---|---|---|
| D1 | Song editions | One song list, as on kancional.cz; no edition model. OL/HK footnotes become `alternative` rules with a note (§6.1). |
| D2 | DB | SQLite on a Fly volume. |
| D3 | v1 song flags | Prefill: `True` → `'*'`, `False` → `NULL` (§6.4). |
| D4 | Plan | Core feature, named **Detailní doporučení** (§8.3). |
| D5 | Occasions page | In v2 (M4). |
| D6 | Author rules | Kept, labelled "doporučení autora". |
| D7 | Several prescribed songs for one part | Valid; not a lint error (§7.3). |
| D8 | Verse hints | Only specific verse numbers are shown; "not verified" stays in the admin (§8.2). |
| D9 | Cookies | Preference cookie only, no banner; fonts self-hosted (§9.5). |
| D10 | Transcription | I draft the YAML from the scan at M3; you review it (§12). |

No open questions right now. Next step: start M1.
