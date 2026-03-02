import json
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

    # Startseite
    tmpl_uebersicht = env.get_template("uebersicht.html")
    (ausgabe_pfad / "index.html").write_text(
        tmpl_uebersicht.render(reisen=reisen, site_root=""),
        encoding="utf-8",
    )

    tmpl_reise = env.get_template("reise.html")
    tmpl_tag = env.get_template("tag.html")
    eintraege_gesamt = 0
    fotos_gesamt = 0

    for reise in reisen:
        reise_ausgabe = ausgabe_pfad / reise.slug
        reise_ausgabe.mkdir(parents=True, exist_ok=True)

        # GeoJSON für Leaflet-Karte
        (reise_ausgabe / "route.geojson").write_text(
            json.dumps(_reise_zu_geojson(reise), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # Reiseseite
        (reise_ausgabe / "index.html").write_text(
            tmpl_reise.render(reise=reise, site_root="../"),
            encoding="utf-8",
        )

        # Tageseinträge
        if reise.eintraege:
            tage_ausgabe = reise_ausgabe / "tage"
            tage_ausgabe.mkdir(exist_ok=True)

            for i, eintrag in enumerate(reise.eintraege):
                vorheriger = reise.eintraege[i - 1] if i > 0 else None
                naechster = reise.eintraege[i + 1] if i < len(reise.eintraege) - 1 else None

                eintrag_ausgabe = tage_ausgabe / eintrag.slug
                eintrag_ausgabe.mkdir(exist_ok=True)

                (eintrag_ausgabe / "index.html").write_text(
                    tmpl_tag.render(
                        reise=reise,
                        eintrag=eintrag,
                        vorheriger=vorheriger,
                        naechster=naechster,
                        site_root="../../../",
                    ),
                    encoding="utf-8",
                )
                eintraege_gesamt += 1

        # Fotos kopieren
        if reise.fotos:
            fotos_quelle = Path("reisen") / reise.slug / "fotos"
            fotos_ziel = reise_ausgabe / "fotos"
            if fotos_quelle.exists():
                fotos_ziel.mkdir(exist_ok=True)
                for foto in reise.fotos:
                    quelle_datei = fotos_quelle / foto.dateiname
                    if quelle_datei.exists():
                        shutil.copy2(quelle_datei, fotos_ziel / foto.dateiname)
                        fotos_gesamt += 1

    # Statische Dateien kopieren
    if statisch_pfad.exists():
        ausgabe_statisch = ausgabe_pfad / "statisch"
        if ausgabe_statisch.exists():
            shutil.rmtree(ausgabe_statisch)
        shutil.copytree(statisch_pfad, ausgabe_statisch)

    teile = [
        f"1 Startseite",
        f"{len(reisen)} Reise(n)",
        f"{eintraege_gesamt} Tageseintrag/-einträge",
        f"{fotos_gesamt} Foto(s)",
    ]
    print(f"Generiert: {', '.join(teile)}")


def _reise_zu_geojson(reise: Reise) -> dict:
    features = []

    koordinaten = [[e.lon, e.lat] for e in reise.etappen]
    if koordinaten:
        features.append({
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": koordinaten},
            "properties": {"typ": "route"},
        })

    for i, etappe in enumerate(reise.etappen, 1):
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [etappe.lon, etappe.lat]},
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
