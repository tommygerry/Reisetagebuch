import shutil
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from .models import Reise


def generiere_website(
    reisen: list[Reise],
    ausgabe_pfad: Path,
    vorlagen_pfad: Path,
    statisch_pfad: Path,
) -> None:
    ausgabe_pfad.mkdir(parents=True, exist_ok=True)

    env = Environment(
        loader=FileSystemLoader(str(vorlagen_pfad)),
        autoescape=True,
    )
    env.globals["site_root"] = "../"

    # Startseite
    tmpl_uebersicht = env.get_template("uebersicht.html")
    (ausgabe_pfad / "index.html").write_text(
        tmpl_uebersicht.render(reisen=reisen, site_root=""),
        encoding="utf-8",
    )

    # Einzelne Reiseseiten
    tmpl_reise = env.get_template("reise.html")
    for reise in reisen:
        reise_ausgabe = ausgabe_pfad / reise.slug
        reise_ausgabe.mkdir(parents=True, exist_ok=True)

        geojson = _reise_zu_geojson(reise)
        (reise_ausgabe / "route.geojson").write_text(
            _geojson_zu_text(geojson),
            encoding="utf-8",
        )

        html = tmpl_reise.render(reise=reise, site_root="../")
        (reise_ausgabe / "index.html").write_text(html, encoding="utf-8")

    # Statische Dateien kopieren
    if statisch_pfad.exists():
        ausgabe_statisch = ausgabe_pfad / "statisch"
        if ausgabe_statisch.exists():
            shutil.rmtree(ausgabe_statisch)
        shutil.copytree(statisch_pfad, ausgabe_statisch)

    print(f"Generiert: 1 Startseite + {len(reisen)} Reise(n)")


def _reise_zu_geojson(reise: Reise) -> dict:
    features = []

    # Routenlinie: Anreise → Etappen → Abreise (zurück zum Heimatort)
    koordinaten = [[e.lon, e.lat] for e in reise.etappen]
    if koordinaten:
        features.append({
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": koordinaten},
            "properties": {"typ": "route"},
        })

    # Marker für jede Etappe
    for i, etappe in enumerate(reise.etappen, 1):
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [etappe.lon, etappe.lat],
            },
            "properties": {
                "typ": "etappe",
                "nummer": i,
                "ort": etappe.ort,
                "naechte": etappe.naechte,
                "ankunft": str(etappe.ankunft),
                "abreise": str(etappe.abreise),
                "unterkunft": etappe.unterkunft,
                "notizen": etappe.notizen,
            },
        })

    return {"type": "FeatureCollection", "features": features}


def _geojson_zu_text(geojson: dict) -> str:
    import json
    return json.dumps(geojson, ensure_ascii=False, indent=2)
