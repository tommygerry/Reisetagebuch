# CLAUDE.md

This file provides guidance for AI assistants working in this repository.

## Project Overview

**Reisetagebuch** (German: "Travel Diary") is a tool for creating travel diaries with automatic
website generation ("Tagebuch für Reisen mit automatischer Website Generierung").

**Current status:** Features 1–4 implemented (trip planning, diary entries, photo galleries,
automated deployment via GitHub Actions → GitHub Pages).

## Repository Structure

```
Reisetagebuch/
├── reisetagebuch/             # Python package (application logic)
│   ├── __init__.py
│   ├── models.py              # Dataclasses: Reise, Etappe, Anreise, Abreise, Foto, Tageseintrag
│   ├── loader.py              # Load + validate YAML trip files, Markdown entries, photos (EXIF)
│   └── generator.py           # Render Jinja2 templates → static HTML, copy photos
├── vorlagen/                  # Jinja2 HTML templates
│   ├── basis.html             # Base layout with Leaflet + GLightbox CDN
│   ├── uebersicht.html        # Homepage: list of all trips
│   ├── reise.html             # Single trip: stage table + map + diary list + photo gallery
│   └── tag.html               # Single diary entry: text + day photos + prev/next nav
├── statisch/
│   └── stil.css               # Site-wide CSS (no external framework)
├── reisen/                    # User trip data (one subdirectory per trip)
│   └── beispiel-2026-italien/
│       ├── reise.yaml         # Trip definition (Rom → Florenz → Venedig)
│       ├── tage/              # Diary entries: YYYY-MM-DD.md with YAML front matter
│       │   ├── 2026-06-01.md
│       │   └── ...
│       └── fotos/             # Photos (JPEG/PNG/WebP/…)
│           ├── fotos.yaml     # Optional captions & alt text per photo
│           └── *.jpg
├── .github/
│   └── workflows/
│       ├── deploy.yml         # Push to master/main → validate → build → GitHub Pages
│       └── validate.yml       # Pull request → validate + build smoke-test
├── ausgabe/                   # Generated website output (gitignored)
├── main.py                    # Entry point: python main.py validate|build
├── requirements.txt           # PyYAML, Jinja2, Markdown, exifread
├── .gitignore
├── LICENSE                    # MIT License (Copyright 2026)
└── CLAUDE.md                  # This file
```

## Tech Stack

| Component | Choice | Reason |
|---|---|---|
| Language | Python 3.11 | Available in environment; great YAML/template ecosystem |
| Trip data | YAML | Human-readable, git-friendly, supports partial specification |
| Diary entries | Markdown + YAML front matter | Writer-friendly, git-diffable |
| Photo metadata | EXIF (exifread) | DateTimeOriginal + GPS from camera/phone without renaming |
| Templating | Jinja2 3.1 | Already installed; industry standard for Python static sites |
| Maps | Leaflet.js (CDN) | Zero build step; renders GeoJSON route and stage markers |
| Lightbox | GLightbox (CDN) | Fullscreen photo viewer with prev/next, zero build step |
| Output | Static HTML/CSS/JS | Deploy to GitHub Pages or Netlify with no server needed |
| CI/CD | GitHub Actions | Free for public repos; native Pages integration |

## Development Workflow

### Prerequisites

```bash
# Python 3.11+ required. Install dependencies:
pip install -r requirements.txt
```

### Commands

```bash
# Validate all trips (checks date consistency and overnight counts)
python main.py validate

# Validate a single trip
python main.py validate beispiel-2026-italien

# Generate the website into ausgabe/
python main.py build

# Serve locally for preview
python3 -m http.server 8000 --directory ausgabe/
# → open http://localhost:8000
```

### Adding a New Trip

1. Create a directory under `reisen/`, e.g. `reisen/meine-reise-2027/`
2. Create `reise.yaml` following the schema below
3. Run `python main.py validate meine-reise-2027` to check for errors
4. Optionally add diary entries in `reisen/meine-reise-2027/tage/YYYY-MM-DD.md`
5. Optionally add photos in `reisen/meine-reise-2027/fotos/`
6. Run `python main.py build` to regenerate the website

### GitHub Pages Deployment Setup

1. Push the repository to GitHub
2. Go to **Settings → Pages** in the GitHub repository
3. Under "Build and deployment", select **Source: GitHub Actions**
4. Push to `master` or `main` — the `deploy.yml` workflow runs automatically:
   - Validates all trips (exits with error if any validation fails)
   - Builds the website into `ausgabe/`
   - Publishes `ausgabe/` to GitHub Pages
5. The site URL is shown in the workflow output and in Settings → Pages

Pull requests trigger `validate.yml`, which validates all trips and runs a build
smoke-test without deploying.

### Branching

- Default branch: `master`
- Remote tracking branch: `origin/main`
- Feature branches follow the pattern: `claude/<description>-<id>`

### Git Conventions

- Commit messages in the imperative mood (e.g., "Add trip planning feature")
- Push feature branches with: `git push -u origin <branch-name>`

## Trip Data Schema (`reise.yaml`)

```yaml
titel: "Reisename"              # Required
beschreibung: "Kurzbeschreibung"
deckbild: ""                    # Optional path to cover image

anreise:
  datum: 2026-06-01             # Required (YYYY-MM-DD)
  von: "München"
  verkehrsmittel: "Flugzeug"    # Flugzeug | Zug | Auto | Bus | Schiff | Fähre

abreise:
  datum: 2026-06-09             # Required; must be after anreise.datum
  nach: "München"
  verkehrsmittel: "Flugzeug"

etappen:
  - ort: "Rom"                  # Required
    lat: 41.9028                # Required (WGS84 decimal degrees)
    lon: 12.4964                # Required
    ankunft: 2026-06-01         # Required; first etappe must match anreise.datum
    naechte: 3                  # Required; abreise is computed as ankunft + naechte
    unterkunft: "Hotel Name"    # Optional
    verkehrsmittel_weiter: "Zug"  # Optional
    notizen: "Highlights"       # Optional
```

**Validation rules enforced by `loader.py`:**
- `etappen[0].ankunft` must equal `anreise.datum`
- `etappen[-1].abreise` (= `ankunft + naechte`) must equal `abreise.datum`
- Consecutive stages must be contiguous: `etappen[i].abreise == etappen[i+1].ankunft`
- `sum(e.naechte)` must equal `(abreise.datum - anreise.datum).days`

## Diary Entry Schema (`tage/YYYY-MM-DD.md`)

```markdown
---
titel: "Heute in Rom"           # Required; fallback: DD.MM.YYYY
ort: "Rom"                      # Optional; shown as location chip
wetter: "sonnig, 28°C"          # Optional
stimmung: "begeistert"          # Optional; mood emoji or text
---

Free **Markdown** text here. Supports headings, lists, blockquotes, links.
```

- Files outside the trip's date range are silently ignored
- Files with non-date stems (not `YYYY-MM-DD.md`) are ignored

## Photo Schema (`fotos/`)

Place any JPEG/PNG/WebP/GIF/AVIF/TIFF images in `reisen/<slug>/fotos/`.

**Assignment priority:**
1. **EXIF `DateTimeOriginal`** — read automatically from camera/phone JPEGs
2. **Filename prefix** `YYYY-MM-DD_name.jpg` — fallback if no EXIF date
3. **EXIF GPS coordinates** — Haversine proximity (≤ 80 km) if no date available

**Optional `fotos.yaml`** for captions:
```yaml
kolosseum.jpg:
  beschriftung: "Das Kolosseum im Nachmittagslicht"
  alt: "Kolosseum in Rom"
```

## Key Modules

### `reisetagebuch/models.py`
Core dataclasses. `Etappe.abreise` is computed automatically from `ankunft + naechte`.
`Reise.gesamtnaechte` and `Reise.gesamttage` are computed properties.
`Etappe.fotos` and `Tageseintrag.fotos` are populated by the loader after EXIF reading.

### `reisetagebuch/loader.py`
- `lade_reise(verzeichnis: Path) -> Reise` — loads and validates one trip directory
- `lade_alle_reisen(reisen_pfad: Path) -> list[Reise]` — loads all trips
- Reads EXIF via `exifread` (optional; graceful fallback if not installed)
- GPS proximity uses Haversine formula with 80 km threshold
- Raises `ValidationFehler` with descriptive German error messages on invalid data

### `reisetagebuch/generator.py`
- `generiere_website(reisen, ausgabe_pfad, vorlagen_pfad, statisch_pfad)` — renders all HTML
- Writes `route.geojson` per trip (consumed by Leaflet.js)
- Copies `fotos/` directory to output (only image files referenced in `reise.fotos`)
- Generates `ausgabe/<slug>/tage/<YYYY-MM-DD>/index.html` per diary entry

## Testing

No test framework configured yet. Manual testing:

```bash
python main.py validate           # validates all trips
python main.py build              # generates ausgabe/
ls ausgabe/                       # index.html + trip subdirectory + statisch/
ls ausgabe/beispiel-2026-italien/ # index.html + route.geojson + tage/ + fotos/
```

## License

MIT — see [LICENSE](./LICENSE) for details.
