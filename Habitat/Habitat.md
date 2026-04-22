# Habitat Master List Updater — Reference

**Location:** `C:\Users\User\Desktop\Habitat_MasterList_Updater\`
**Purpose:** Automated tool to maintain and enrich a species Habitat Master List (Fauna + Flora) used for Likelihood of Occurrence (LOO) ecological assessments.  
**Organisation:** BAAM Ecology

---

## Directory Structure

```
Habitat_MasterList_Updater\
├── config\
│   └── config.yaml                   — Main configuration file
├── logs\                              — (empty; alerts go to out\)
├── out\                               — Generated outputs (changelogs, review queues, alerts, backups)
│   ├── ALERT_<date>.txt
│   ├── Changelog_<date>.csv
│   ├── Review_Queue_<date>.xlsx
│   └── Habitat Master List_WORKING_backup_<date>.xlsx
├── src\                               — All Python source code
│   ├── sources\                       — External API client modules
│   │   ├── ala.py                     — Atlas of Living Australia (name match)
│   │   ├── ala_bie.py                 — ALA BIE species profile (habitat text, API + HTML page)
│   │   ├── biocache.py                — ALA Biocache occurrence facets
│   │   ├── birdlife.py                — BirdLife Australia habitat text
│   │   ├── ebird.py                   — eBird (Cornell Lab of Ornithology) habitat text [Fauna]
│   │   ├── hanzab.py                  — HANZAB online with OAuth 2.0 login [Fauna/birds]
│   │   ├── iucn.py                    — IUCN Red List narrative
│   │   ├── reptiledb.py               — The Reptile Database habitat text [Fauna]
│   │   ├── sprat.py                   — SPRAT (Australian Gov. species profiles)
│   │   └── wildnet.py                 — WildNet (Queensland species list)
│   ├── excel_io.py                    — Excel load/save helpers, SheetLoadResult dataclass
│   ├── gui_app.py                     — Tkinter GUI (5-tab desktop interface)
│   ├── review_queue.py                — Flag computation + review queue builder
│   ├── runner_daily.py                — Orchestrates phases 4→5→7→8→6→9 in sequence
│   ├── runner_phase1_init.py          — Phase 1: init WORKING file from master
│   ├── runner_phase2_scaffold_schema.py — Phase 2: add missing columns to WORKING
│   ├── runner_phase3.py               — Phase 3: blank-field report / validation check
│   ├── runner_phase4_ala_fill.py      — Phase 4: fill ALA_GUID, canonical name, common name
│   ├── runner_phase5_wildnet_fill.py  — Phase 5: fill WILDNET_TAXON_ID, common name (QLD)
│   ├── runner_phase6_review_queue.py  — Phase 6: generate Review_Queue + Changelog
│   ├── runner_phase7_change_detect.py — Phase 7: hash-based change detection vs ALA/WildNet
│   ├── runner_phase8_biocache_habitat_suggest.py — Phase 8: suggest habitat from biocache facets (on-demand only)
│   ├── runner_phase9_claude_synth.py  — Phase 9: source gathering + AI extraction (SPRAT/ALA/BirdLife/HANZAB/eBird)
│   ├── runner_phase10_sprat_id_fill.py — Phase 10: auto-fill SPRAT_ID by searching SPRAT per species
│   └── state_db.py                   — SQLite state + change log + audit log
├── state\
│   ├── state.db                       — SQLite database (species state, change log, audit log)
│   └── phase9_progress.json           — Live progress file for GUI polling
├── Habitat Master List.xlsx           — Master (read-only source of truth)
├── Habitat Master List_WORKING.xlsx   — Working copy (automation writes here)
├── Habitat Master List_BASELINE_2026-01-19.xlsx — Baseline snapshot
├── Habitat Master List_WORKING_NEW_2026-04-13.xlsx — Overflow if WORKING locked in Excel
├── requirements.txt
├── run_daily.bat                      — Run daily pipeline (calls runner_daily.py)
└── run_gui.bat                        — Launch GUI (calls gui_app.py)
```

---

## Dependencies (`requirements.txt`)

```
pandas>=2.1
openpyxl>=3.1
requests>=2.31
python-dateutil>=2.8
tqdm>=4.66
anthropic>=0.40
PyYAML>=6.0
beautifulsoup4>=4.12
```

Python virtual environment: `.venv\Scripts\python.exe`

---

## Configuration (`config\config.yaml`)

```yaml
paths:
  master_excel:  "...Habitat Master List.xlsx"
  working_excel: "...Habitat Master List_WORKING.xlsx"
  out_dir:       "...out"
  state_db:      "...state\state.db"

ala:
  base_url:   "https://api.ala.org.au"
  user_agent: "BAAM-HabitatMasterList-Updater/1.0 (contact: BAAM Ecology)"
  sleep_s:    0.25

wildnet:
  base_url:   "https://wildnet-pub.science-data.qld.gov.au"
  user_agent: "BAAM-HabitatMasterList-Updater/1.0 (contact: BAAM Ecology)"
  sleep_s:    0.25

iucn:
  token: ""   # Register at apiv3.iucnredlist.org; leave blank to skip IUCN lookups

hanzab:
  email: "arosso@baamecology.com"    # HANZAB OAuth login (BirdLife Australia)
  password: "Digbyioane1!"           # Used only if unauthenticated access is blocked

anthropic:
  model:                    "claude-sonnet-4-6"
  max_tokens:               2048
  max_search_turns:         6
  delay_between_species_s:  1.5
  species_per_run:          0   # 0 = no limit

synthesis:
  overwrite_existing_habitat:  false  # true = re-synthesise all
  auto_apply_if_blank:         false  # true = write directly to Preferred Habitat Characteristics

rules:
  fill_common_name_if_blank:       true
  fill_reference_if_blank:         true
  overwrite_existing_common_name:  false
  overwrite_existing_reference:    false
```

---

## Excel Schema — WORKING File

Both sheets (`Fauna`, `Flora`) use the same **19-column** schema (as of April 2026 overhaul):

| # | Column | Type | Description |
|---|--------|------|-------------|
| 1 | `Scientific Name` | human | Binomial species name (row key) |
| 2 | `Common Name` | human/auto | Vernacular name; auto-filled if blank |
| 3 | `Preferred Habitat Characteristics` | human | **Primary field** — habitat synopsis for LOO |
| 4 | `Reference` | human/auto | Pipe-separated citations; auto-appended |
| 5 | `CANONICAL_SCI_NAME` | auto | ALA-normalised scientific name |
| 6 | `ALA_GUID` | auto | Atlas of Living Australia GUID |
| 7 | `WILDNET_TAXON_ID` | auto | WildNet QLD taxon ID |
| 8 | `SPRAT_ID` | manual | Australian Gov. SPRAT species ID (if known) |
| 9 | `SUGGESTED_HABITAT_TEXT` | auto | AI-generated habitat synopsis (awaiting review) |
| 10 | `SUGGESTED_HABITAT_SOURCE` | auto | Reference/URL for the accepted source text |
| 11 | `SOURCES_CHECKED` | auto | All sources checked, with found/not-found status (pipe-separated) |
| 12 | `LAST_CHECKED_UTC` | auto | ISO8601 UTC timestamp of last automation check |
| 12 | `LAST_CHANGED_UTC` | auto | ISO8601 UTC timestamp of last detected change |
| 13 | `CHANGE_TYPES` | auto | Pipe-separated change sources (e.g. `ALA | WILDNET`) |
| 14 | `CHANGE_SUMMARY` | auto | Human-readable change description |
| 15 | `REVIEW_STATUS` | auto/human | e.g. `Pending`, `Pending (AI suggestion)`, `AI-applied` |
| 16 | `REVIEWER` | human | Who reviewed the row |
| 17 | `REVIEW_NOTES` | auto/human | Free text + Claude confidence tags |
| 18 | `AUTO_UPDATE_ALLOWED` | human | Whether automation may overwrite human data |

**Column alias normalisation** (typo variants in master are auto-corrected):
- `Preferred Habitat Characteritics` → `Preferred Habitat Characteristics`
- `Preferred Habitat Charactersitics` → `Preferred Habitat Characteristics`
- `Preferred Habitat Characteristcs` → `Preferred Habitat Characteristics`
- `Preferred Habitat Characterisitcs` → `Preferred Habitat Characteristics`

---

## Phases

### Phase 1 — Initialise Working File (`runner_phase1_init.py`)
- Copies master → WORKING; normalises column typos; scaffolds full 18-column schema.
- Merges automation columns from existing WORKING (preserves GUIDs, review data) without overwriting human-authored master columns.
- Backups existing WORKING to `out\Habitat Master List_WORKING_backup_<date>.xlsx`.
- Handles Windows Excel lock: writes to `WORKING_NEW_<date>.xlsx` if WORKING is open.
- **Run once** on setup, or whenever master has been updated.

```
python src\runner_phase1_init.py
python src\runner_phase1_init.py --force   # overwrite WORKING even if it exists
```

### Phase 2 — Scaffold Schema (`runner_phase2_scaffold_schema.py`)
- Adds any missing required columns to WORKING and reorders to schema order.
- Standalone utility (Phase 1 now handles this internally).

```
python src\runner_phase2_scaffold_schema.py
```

### Phase 3 — Validation Check (`runner_phase3.py`)
- Loads WORKING and prints a blank-field report for all key columns.
- Shows count/percentage of blank cells per column per sheet.
- Read-only — does not modify files.

```
python src\runner_phase3.py
```

### Phase 4 — ALA Fill (`runner_phase4_ala_fill.py`)
- For each species: calls ALA name-match API to get `CANONICAL_SCI_NAME`, `ALA_GUID`, `Common Name`.
- Appends `ALA (guid=...)` reference if `fill_reference_if_blank` is true.
- Only fills blank cells (respects `overwrite_existing_common_name` / `overwrite_existing_reference` config).
- Updates `LAST_CHECKED_UTC`.

```
python src\runner_phase4_ala_fill.py
```

### Phase 5 — WildNet Fill (`runner_phase5_wildnet_fill.py`)
- For each species: queries WildNet species-list API to get `WILDNET_TAXON_ID`, `Common Name` (QLD authority).
- Appends `WildNet API species-list (taxon_id=...)` reference.
- Only fills blank cells (Common Name only if WildNet returns one).

```
python src\runner_phase5_wildnet_fill.py
```

### Phase 6 — Review Queue (`runner_phase6_review_queue.py`)
- Runs `build_review_queue()` on each sheet.
- Generates:
  - `out\Review_Queue_<date>.xlsx` — all flagged rows, sorted by priority
  - `out\Changelog_<date>.csv` — one row per flag event

**Flag types and priorities:**

| Flag | Priority | Condition |
|------|----------|-----------|
| `HABITAT_BLANK` | 100 | `Preferred Habitat Characteristics` is empty |
| `SOURCE_CHANGE` | 90 | `CHANGE_TYPES` column is populated |
| `GROUP_ROW_HABITAT_BLANK` | 90 | Group/multi-taxa row: habitat blank |
| `GROUP_ROW_REFERENCE_BLANK` | 70 | Group/multi-taxa row: reference blank |
| `REFERENCE_BLANK` | 60 | `Reference` is blank |
| `ALA_GUID_BLANK` | 55 | `ALA_GUID` missing |
| `WILDNET_ID_BLANK` | 55 | `WILDNET_TAXON_ID` missing |
| `COMMON_NAME_BLANK` | 40 | `Common Name` blank |
| `GROUP_ROW` | 50 | Row is a group label (has `,`, `:`, `spp.`, etc.) |

```
python src\runner_phase6_review_queue.py
```

### Phase 7 — Change Detection (`runner_phase7_change_detect.py`)
- Re-queries ALA + WildNet for every species; computes payload hashes.
- Compares against stored hashes in `state.db`; records changes in `change_log` table.
- Writes `CHANGE_TYPES` + `CHANGE_SUMMARY` + `LAST_CHANGED_UTC` to WORKING.
- Writes `out\ALERT_<date>.txt` if any changes detected.

```
python src\runner_phase7_change_detect.py
```

### Phase 8 — Biocache Habitat Suggest (`runner_phase8_biocache_habitat_suggest.py`)
- For species with blank habitat AND blank suggestion: fetches ALA Biocache occurrence facets (IBRA bioregions + states).
- Builds a habitat evidence text string and writes to `SUGGESTED_HABITAT_TEXT`.
- Requires `ALA_GUID` to be filled.

```
python src\runner_phase8_biocache_habitat_suggest.py
```

### Phase 9 — Habitat Source Gathering + AI Extraction (`runner_phase9_claude_synth.py`)

**Architecture:** extraction-first (never synthesises). Scrapers pull verbatim text; Claude selects and validates.

For species missing `Preferred Habitat Characteristics` (and `SUGGESTED_HABITAT_TEXT` unless `--force`):

1. **Deterministic scrapers** gather verbatim "Habitat" section text from each source in priority order:

| Priority | Source | Scope |
|----------|--------|-------|
| 1 | SPRAT (Australian Gov. species profiles) | All species with a SPRAT_ID |
| 2 | ALA BIE (species profile — API + HTML page) | All species with an ALA_GUID |
| 3 | BirdLife Australia | Fauna only |
| 3 | HANZAB online (hanzab.birdlife.org.au) | Fauna / birds; OAuth login with configured credentials |
| 4 | eBird — Cornell Lab of Ornithology | Fauna / birds |
| 5 | The Reptile Database | Fauna — reptiles |
| 6 | IUCN Red List | All species (requires free API token in config) |
| fallback | Claude `web_search` | Only when ALL scrapers return empty |

2. **Claude validation** (no web_search at this stage):
   - Selects the best verbatim text (priority: SPRAT > ALA BIE > BirdLife > HANZAB > eBird > IUCN > Reptile DB).
   - May combine complementary sentences from multiple sources — verbatim only, no paraphrasing.
   - Appends **in-text APA citation** at end of selected text, e.g. `...box-ironbark woodland (DCCEEW, 2024; ALA, n.d.)`.
   - Generates **full APA 7th edition references** for every contributing source.
   - Checks **geographic relevance** for Brigalow Belt, New England Tableland, South East Queensland.

3. **Claude web_search fallback** (only when all scrapers return empty):
   - Directed to find verbatim text on SPRAT / ALA / BirdLife / eBird pages — NOT to generate text.

4. **Writes** to:
   - `SUGGESTED_HABITAT_TEXT` — verbatim text with in-text citations appended.
   - `SUGGESTED_HABITAT_SOURCE` — full APA references (newline-separated if multiple).
   - `SOURCES_CHECKED` — pipe-separated record of every source tried (FOUND / not found).
   - `REVIEW_NOTES` — relevance badge, primary source, contributing sources.
   - If `auto_apply_if_blank=true`: also writes to `Preferred Habitat Characteristics` + `Reference`.

5. **Never overwrites** `Preferred Habitat Characteristics` automatically — all suggestions go to `SUGGESTED_*` columns first.

**APA referencing convention:**

| Source | In-text | Full reference template |
|--------|---------|------------------------|
| SPRAT | `(DCCEEW, 2024)` | `Department of Climate Change, Energy, the Environment and Water (DCCEEW). (2024). [Species] — Species profile. Retrieved [date], from [url]` |
| ALA BIE | `(ALA, n.d.)` | `Atlas of Living Australia (ALA). (n.d.). [Species]. Retrieved [date], from [url]` |
| BirdLife Australia | `(BirdLife Australia, n.d.)` | `BirdLife Australia. (n.d.). [Common name]. Retrieved [date], from [url]` |
| HANZAB | `(Marchant & Higgins, 1990–2006)` | `Marchant, S., & Higgins, P. J. (Eds.). (1990–2006). Handbook of Australian, New Zealand and Antarctic Birds (Vols. 1–7). Oxford University Press.` |
| eBird | `(Cornell Lab of Ornithology, n.d.)` | `Cornell Lab of Ornithology. (n.d.). [Species]. eBird. Retrieved [date], from [url]` |
| IUCN | `(IUCN, 2024)` | `IUCN. (2024). [Species]. The IUCN Red List of Threatened Species. Retrieved [date], from [url]` |
| Reptile DB | `(Uetz et al., n.d.)` | `Uetz, P., Freed, P., Aguilar, R., Reyes, F., & Hošek, J. (Eds.). (n.d.). [Species]. The Reptile Database. Retrieved [date], from [url]` |

If the same habitat information is confirmed across multiple sources, **all contributing sources are cited** (in-text and in references).

```
python src\runner_phase9_claude_synth.py
python src\runner_phase9_claude_synth.py --limit 10
python src\runner_phase9_claude_synth.py --force          # re-run all, including those already done
python src\runner_phase9_claude_synth.py --species "Acacia attenuata"
python src\runner_phase9_claude_synth.py --auto-apply     # write directly to main columns
python src\runner_phase9_claude_synth.py --sheet Fauna    # Fauna sheet only
python src\runner_phase9_claude_synth.py --api-key sk-ant-...
```

### Phase 10 — SPRAT ID Auto-Fill (`runner_phase10_sprat_id_fill.py`)

Searches the SPRAT database by scientific name for every species where `SPRAT_ID` is blank, and fills in the numeric taxon ID.

**Why this matters:** SPRAT is the Priority 1 source in Phase 9. Without a `SPRAT_ID`, Phase 9 skips SPRAT entirely for that species — even if the species is EPBC-listed and has a rich habitat profile. Phase 10 runs before Phase 9 in the daily pipeline to ensure maximum SPRAT coverage.

**Behaviour:**
- Non-destructive — only fills blank `SPRAT_ID` cells, never overwrites.
- Species not listed under the EPBC Act will return "not listed in SPRAT" — this is expected and logged, not an error.
- Writes a dated Excel report to `out/SPRAT_ID_Fill_<date>.xlsx` showing every result.
- Every search is logged to the `audit_log` table in `state.db`.

**Search strategy:**
1. Hits `SPRAT_SEARCH_BASE` with multiple parameter variants (handles SPRAT form version differences).
2. If a single result is returned as a redirect to a species profile, extracts the `taxon_id` from the URL and validates via name similarity.
3. Falls back to the threatened species list page filtered by name.
4. Uses token-overlap similarity scoring — tolerates minor name differences (subspecies epithets, author names).

```
python src\runner_phase10_sprat_id_fill.py
python src\runner_phase10_sprat_id_fill.py --force          # re-check species that already have an ID
python src\runner_phase10_sprat_id_fill.py --sheet Fauna
python src\runner_phase10_sprat_id_fill.py --species "Acacia attenuata"
python src\runner_phase10_sprat_id_fill.py --limit 50
```

After Phase 10 fills new IDs, re-run Phase 9 with `--force` for those species to retrieve SPRAT habitat text.

---

## Daily Runner (`runner_daily.py`)

Orchestrates the full pipeline in sequence:
```
Phase 4 → Phase 5 → Phase 10 → Phase 7 → Phase 6 → Phase 9 (if API key set)
```

Phase 8 (Biocache suggest) is no longer in the daily run — it is superseded by
Phase 9's direct scraping. Run it manually if needed.

Options:
```
python src\runner_daily.py
python src\runner_daily.py --skip-claude        # skip Phase 9
python src\runner_daily.py --only-claude        # run Phase 9 only
python src\runner_daily.py --skip-sprat-fill    # skip Phase 10 (once IDs are mostly populated)
python src\runner_daily.py --only-sprat-fill    # run Phase 10 only
```

Batch launcher: `run_daily.bat`

---

## GUI (`gui_app.py`)

Tkinter desktop app launched via `run_gui.bat`. Six tabs:

| Tab | Purpose |
|-----|---------|
| **Species List** | Live colour-coded table of every species (status, relevance, last checked, sources). |
| **Review Queue** | Split-pane review interface: current habitat (green) vs AI suggestion (yellow) side-by-side. Action buttons: Accept, Edit then Accept, Reject, Skip. Batch: Accept All Relevant, Reject All Low Relevance. Sources Checked displayed one per line. Auto-reloads after Phase 9 completes. |
| **Run & Progress** | Buttons for every phase; real-time per-species progress bar and live log during Phase 9. "Go to Review Queue →" shortcut after Phase 9. |
| **Audit Log** | Full history of every source checked and every write made by automation; filterable; exportable. |
| **Export** | Generate clean Excel (4 core columns only), full WORKING copy, or audit CSV — saved anywhere. |
| **Settings** | API key entry, IUCN token note, column reference guide. |

**Review Queue — row colours:**
- Green (`relevant`) — habitat is consistent with Brigalow Belt / New England Tableland / SEQ
- Red (`low_relevance`) — habitat inconsistent with work area
- Yellow (`uncertain`) — insufficient information to judge

**Row status colours:**
- `Complete` — dark green text, light green background (habitat filled)
- `AI-applied` — amber text, yellow background
- `AI suggestion` — orange text, peach background (suggested, awaiting review)
- `Missing` — red text, pink background

---

## State Database (`state\state.db`) — SQLite

Three tables:

### `species_state`
Stores latest API hashes per species for change detection.

| Column | Type | Notes |
|--------|------|-------|
| `key` | TEXT PK | `"Sheet::Scientific Name"` |
| `sheet` | TEXT | `Fauna` or `Flora` |
| `scientific_name` | TEXT | |
| `ala_guid` | TEXT | |
| `wildnet_taxon_id` | TEXT | |
| `ala_hash` | TEXT | Hash of ALA API payload |
| `wildnet_hash` | TEXT | Hash of WildNet API payload |
| `last_checked_utc` | TEXT | ISO8601 |
| `last_changed_utc` | TEXT | ISO8601 (nullable) |

### `change_log`
Append-only log of detected API-level changes.

| Column | Notes |
|--------|-------|
| `key` | Species key |
| `source` | `ALA` or `WILDNET` |
| `old_hash` / `new_hash` | Before/after payload hashes |
| `changed_utc` | When change was detected |
| `summary` | Human-readable description |

### `audit_log`
Full audit trail of every automation action (Phase 9 and change detection).

| Column | Notes |
|--------|-------|
| `logged_utc` | Timestamp |
| `sheet` / `scientific_name` | Species identity |
| `phase` | Phase number (e.g. `"9"`) |
| `source` | API/system name (e.g. `"Claude"`, `"ALA BIE"`) |
| `action` | e.g. `"SYNTHESISE"`, `"CHECK"` |
| `result` | e.g. `"success"`, `"failed"`, `"found"` |
| `detail` | Supplemental info (confidence, char counts, etc.) |

---

## External APIs

| API / Source | URL | Purpose | Scope |
|---|---|---|---|
| ALA Name Match | `https://api.ala.org.au` | Resolve scientific name → GUID + canonical name + common name | All |
| ALA BIE | `https://bie.ala.org.au/species/{guid}` | Species profile including habitat text (API + HTML page scraping) | All |
| ALA Biocache | `https://api.ala.org.au` | Occurrence facets: IBRA bioregions + states | All |
| WildNet | `https://wildnet-pub.science-data.qld.gov.au` | QLD species list + taxon IDs | All |
| SPRAT | `https://environment.gov.au/cgi-bin/sprat/public/publicspecies.pl?taxon_id={id}` | Australian Gov. threatened species profiles (highest authority) | All |
| BirdLife Australia | `https://www.birdlife.org.au/bird-profile/{slug}/` | Bird habitat text | Fauna |
| HANZAB | `https://hanzab.birdlife.org.au/species/{slug}/` | Handbook of Australian, New Zealand & Antarctic Birds; OAuth 2.0 via `login.birdlife.org.au` | Fauna / birds |
| eBird | `https://ebird.org/species/{code}` | Cornell Lab of Ornithology species pages | Fauna / birds |
| The Reptile Database | `https://reptile-database.reptarium.cz/species?genus={g}&species={s}` | Reptile habitat text | Fauna |
| IUCN Red List | `https://apiv3.iucnredlist.org` | Species narrative (requires free token) | All |
| Claude `web_search` | (built-in tool) | Fallback — extracts verbatim text; only used when ALL scrapers return empty | All |

---

## Outputs Generated

| File | Location | Description |
|------|----------|-------------|
| `Habitat Master List_WORKING.xlsx` | project root | Primary working file (2 sheets: Fauna, Flora) |
| `Habitat Master List_WORKING_backup_<date>.xlsx` | `out\` | Pre-Phase-1 backup |
| `Habitat Master List_WORKING_NEW_<date>.xlsx` | project root | Overflow if WORKING locked in Excel |
| `Review_Queue_<date>.xlsx` | `out\` | Flagged species needing human review |
| `Changelog_<date>.csv` | `out\` | Per-flag audit trail |
| `ALERT_<date>.txt` | `out\` | Alert file when changes detected (Phase 7) |
| `state.db` | `state\` | SQLite database |
| `phase9_progress.json` | `state\` | Live progress for GUI polling |

---

## Recent Activity

- **2026-01-19**: Baseline established (`Habitat Master List_BASELINE_2026-01-19.xlsx`)
- **2026-01-19 / 2026-01-20**: Initial pipeline runs; changelogs and review queues generated
- **2026-04-13**: Full run; 1 change detected (ALA); changelog + review queue regenerated; `ALERT_2026-04-13.txt` written; `Habitat Master List_WORKING_NEW_2026-04-13.xlsx` created (WORKING was locked in Excel at time of run)

---

## Key Code Patterns

- **`is_blank(v)`** — consistent blank-check handling `None`, `NaN`, `"nan"`, `"<NA>"`, `""` across all phases.
- **`append_reference(existing, new_ref)`** — pipe-separates references, deduplicates case-insensitively.
- **Atomic Excel write** — write to `__TMP.xlsx`, then rename/replace to avoid partial writes.
- **Windows Excel lock handling** — catches `PermissionError` on rename; saves to `WORKING_NEW_<date>.xlsx` with user instructions.
- **`SheetLoadResult` dataclass** — carries `(sheet_name, df, dropped_blank_rows)` between phases.
- **Phase 9 agentic loop** — handles `tool_use` stop reason for server-side `web_search`; defensive max-turns cap; JSON extraction with fallback regex.
