# CLAUDE.md

This file provides guidance for AI assistants working in this repository.

## Project Overview

**Reisetagebuch** (German: "Travel Diary") is a tool for creating travel diaries with automatic
website generation ("Tagebuch für Reisen mit automatischer Website Generierung").

**Current status:** Feature 1 (rough trip planning) implemented. No diary entries or photo support yet.

## Repository Structure

```
Reisetagebuch/
├── reisetagebuch/             # Python package (application logic)
│   ├── __init__.py
│   ├── models.py              # Dataclasses: Reise, Etappe, Anreise, Abreise
│   ├── loader.py              # Load + validate YAML trip files
│   └── generator.py           # Render Jinja2 templates → static HTML
├── vorlagen/                  # Jinja2 HTML templates
│   ├── basis.html             # Base layout with Leaflet CDN
│   ├── uebersicht.html        # Homepage: list of all trips
│   └── reise.html             # Single trip: stage table + interactive map
├── statisch/
│   └── stil.css               # Site-wide CSS (no external framework)
├── reisen/                    # User trip data (one subdirectory per trip)
│   └── beispiel-2026-italien/
│       └── reise.yaml         # Example trip (Rom → Florenz → Venedig)
├── ausgabe/                   # Generated website output (gitignored)
├── main.py                    # Entry point: python main.py validate|build
├── requirements.txt           # PyYAML, Jinja2
├── .gitignore
├── LICENSE                    # MIT License (Copyright 2026)
└── CLAUDE.md                  # This file
```

## Tech Stack

| Component | Choice | Reason |
|---|---|---|
| Language | Python 3.11 | Available in environment; great YAML/template ecosystem |
| Trip data | YAML | Human-readable, git-friendly, supports partial specification |
| Templating | Jinja2 3.1 | Already installed; industry standard for Python static sites |
| Maps | Leaflet.js (CDN) | Zero build step; renders GeoJSON route and stage markers |
| Output | Static HTML/CSS/JS | Deploy to GitHub Pages or Netlify with no server needed |

## Development Workflow

### Prerequisites

```bash
# Python 3.11+ required. Dependencies are already installed in this environment:
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
4. Run `python main.py build` to regenerate the website

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

## Key Modules

### `reisetagebuch/models.py`
Core dataclasses. `Etappe.abreise` is computed automatically from `ankunft + naechte`.
`Reise.gesamtnaechte` and `Reise.gesamttage` are computed properties.

### `reisetagebuch/loader.py`
- `lade_reise(verzeichnis: Path) -> Reise` — loads and validates one trip directory
- `lade_alle_reisen(reisen_pfad: Path) -> list[Reise]` — loads all trips
- Raises `ValidationFehler` with descriptive German error messages on invalid data

### `reisetagebuch/generator.py`
- `generiere_website(reisen, ausgabe_pfad, vorlagen_pfad, statisch_pfad)` — renders all HTML
- Also writes `route.geojson` per trip (consumed by Leaflet.js in `reise.html`)

## Testing

No test framework configured yet. Manual testing:

```bash
python main.py validate           # validates beispiel-2026-italien
python main.py build              # generates ausgabe/
ls ausgabe/                       # should contain index.html + trip subdirectory
```

## Planned Features (not yet implemented)

- **Feature 2:** Daily diary entries (Markdown files with YAML front matter)
- **Feature 3:** Photo galleries per stage
- **Feature 4:** Automated deployment (GitHub Actions → GitHub Pages)

## License

MIT — see [LICENSE](./LICENSE) for details.
