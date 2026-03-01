from datetime import date, timedelta
from pathlib import Path

import markdown
import yaml

from .models import Anreise, Abreise, Etappe, Reise, Tageseintrag


class ValidationFehler(Exception):
    pass


def _als_datum(wert, feld: str) -> date:
    if isinstance(wert, date):
        return wert
    try:
        return date.fromisoformat(str(wert))
    except ValueError:
        raise ValidationFehler(f"'{feld}' ist kein gültiges Datum (YYYY-MM-DD): {wert!r}")


def _lade_yaml(pfad: Path) -> dict:
    with pfad.open(encoding="utf-8") as f:
        daten = yaml.safe_load(f)
    if not isinstance(daten, dict):
        raise ValidationFehler(f"{pfad}: Ungültiges YAML-Format (erwartet ein Mapping)")
    return daten


def _parse_markdown_datei(pfad: Path) -> tuple[dict, str]:
    """Liest eine Markdown-Datei mit optionalem YAML-Frontmatter.

    Format:
        ---
        titel: "Heute in Rom"
        ort: "Rom"
        wetter: "sonnig"
        stimmung: "begeistert"
        ---

        Markdown-Text hier...

    Gibt (frontmatter_dict, markdown_text) zurück.
    """
    text = pfad.read_text(encoding="utf-8")
    frontmatter: dict = {}
    body = text

    if text.startswith("---"):
        teile = text.split("---", 2)
        if len(teile) >= 3:
            try:
                frontmatter = yaml.safe_load(teile[1]) or {}
            except yaml.YAMLError:
                frontmatter = {}
            body = teile[2].lstrip("\n")

    return frontmatter, body


def _lade_eintraege(verzeichnis: Path, anreise_datum: date, abreise_datum: date) -> list[Tageseintrag]:
    tage_pfad = verzeichnis / "tage"
    if not tage_pfad.exists():
        return []

    eintraege: list[Tageseintrag] = []
    md = markdown.Markdown(extensions=["extra", "nl2br"])

    for datei in sorted(tage_pfad.glob("*.md")):
        # Dateiname muss YYYY-MM-DD.md sein
        try:
            datum = date.fromisoformat(datei.stem)
        except ValueError:
            continue  # Dateien mit anderem Namensformat ignorieren

        if not (anreise_datum <= datum < abreise_datum):
            continue  # Einträge außerhalb der Reise ignorieren

        frontmatter, body = _parse_markdown_datei(datei)

        md.reset()
        inhalt_html = md.convert(body)

        eintrag = Tageseintrag(
            datum=datum,
            titel=str(frontmatter.get("titel", datum.strftime("%d.%m.%Y"))),
            ort=str(frontmatter.get("ort", "")),
            wetter=str(frontmatter.get("wetter", "")),
            stimmung=str(frontmatter.get("stimmung", "")),
            inhalt_html=inhalt_html,
            slug=datei.stem,
        )
        eintraege.append(eintrag)

    return eintraege


def _parse_etappen(roh: list, anreise_datum: date) -> list[Etappe]:
    etappen: list[Etappe] = []
    vorheriges_abreise: date | None = None

    for i, e in enumerate(roh, start=1):
        nr = f"Etappe {i} ({e.get('ort', '?')})"

        ort = e.get("ort")
        if not ort:
            raise ValidationFehler(f"{nr}: Pflichtfeld 'ort' fehlt")

        try:
            lat = float(e["lat"])
            lon = float(e["lon"])
        except (KeyError, TypeError, ValueError):
            raise ValidationFehler(f"{nr}: 'lat' und 'lon' müssen Dezimalzahlen sein")

        if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
            raise ValidationFehler(f"{nr}: Koordinaten außerhalb des gültigen Bereichs (lat={lat}, lon={lon})")

        if "ankunft" not in e:
            raise ValidationFehler(f"{nr}: Pflichtfeld 'ankunft' fehlt")
        ankunft = _als_datum(e["ankunft"], f"{nr}.ankunft")

        if "naechte" not in e:
            raise ValidationFehler(f"{nr}: Pflichtfeld 'naechte' fehlt")
        try:
            naechte = int(e["naechte"])
        except (TypeError, ValueError):
            raise ValidationFehler(f"{nr}: 'naechte' muss eine ganze Zahl sein")
        if naechte < 1:
            raise ValidationFehler(f"{nr}: 'naechte' muss mindestens 1 sein")

        if "abreise" in e:
            abreise_angabe = _als_datum(e["abreise"], f"{nr}.abreise")
            erwartet = ankunft + timedelta(days=naechte)
            if abreise_angabe != erwartet:
                raise ValidationFehler(
                    f"{nr}: 'abreise' ({abreise_angabe}) stimmt nicht mit "
                    f"ankunft + naechte ({erwartet}) überein"
                )

        etappe = Etappe(
            ort=ort,
            lat=lat,
            lon=lon,
            ankunft=ankunft,
            naechte=naechte,
            unterkunft=e.get("unterkunft", ""),
            verkehrsmittel_weiter=e.get("verkehrsmittel_weiter", ""),
            notizen=e.get("notizen", ""),
        )
        etappen.append(etappe)

        if i == 1:
            if ankunft != anreise_datum:
                raise ValidationFehler(
                    f"Erste Etappe ({ort}): 'ankunft' ({ankunft}) muss dem "
                    f"Anreisedatum ({anreise_datum}) entsprechen"
                )
        else:
            if ankunft != vorheriges_abreise:
                raise ValidationFehler(
                    f"{nr}: 'ankunft' ({ankunft}) muss dem Abreisedatum der "
                    f"vorherigen Etappe ({vorheriges_abreise}) entsprechen – keine Lücken"
                )

        vorheriges_abreise = etappe.abreise

    return etappen


def lade_reise(verzeichnis: Path) -> Reise:
    yaml_pfad = verzeichnis / "reise.yaml"
    if not yaml_pfad.exists():
        raise ValidationFehler(f"Keine reise.yaml in {verzeichnis}")

    d = _lade_yaml(yaml_pfad)

    titel = d.get("titel", "")
    if not titel:
        raise ValidationFehler("Pflichtfeld 'titel' fehlt")

    anreise_roh = d.get("anreise")
    if not anreise_roh or "datum" not in anreise_roh:
        raise ValidationFehler("'anreise.datum' fehlt")
    anreise = Anreise(
        datum=_als_datum(anreise_roh["datum"], "anreise.datum"),
        von=anreise_roh.get("von", ""),
        verkehrsmittel=anreise_roh.get("verkehrsmittel", ""),
    )

    abreise_roh = d.get("abreise")
    if not abreise_roh or "datum" not in abreise_roh:
        raise ValidationFehler("'abreise.datum' fehlt")
    abreise = Abreise(
        datum=_als_datum(abreise_roh["datum"], "abreise.datum"),
        nach=abreise_roh.get("nach", ""),
        verkehrsmittel=abreise_roh.get("verkehrsmittel", ""),
    )

    if abreise.datum <= anreise.datum:
        raise ValidationFehler(
            f"'abreise.datum' ({abreise.datum}) muss nach 'anreise.datum' ({anreise.datum}) liegen"
        )

    etappen_roh = d.get("etappen", [])
    if not etappen_roh:
        raise ValidationFehler("Mindestens eine Etappe muss definiert sein")

    etappen = _parse_etappen(etappen_roh, anreise.datum)

    if etappen[-1].abreise != abreise.datum:
        raise ValidationFehler(
            f"Letzte Etappe ({etappen[-1].ort}): Ende ({etappen[-1].abreise}) muss dem "
            f"Abreisedatum ({abreise.datum}) entsprechen"
        )

    summe = sum(e.naechte for e in etappen)
    gesamt = (abreise.datum - anreise.datum).days
    if summe != gesamt:
        raise ValidationFehler(
            f"Summe der Übernachtungen ({summe}) ≠ Gesamtdauer ({gesamt} Nächte)"
        )

    eintraege = _lade_eintraege(verzeichnis, anreise.datum, abreise.datum)

    return Reise(
        titel=titel,
        beschreibung=d.get("beschreibung", ""),
        anreise=anreise,
        abreise=abreise,
        etappen=etappen,
        eintraege=eintraege,
        deckbild=d.get("deckbild", ""),
        slug=verzeichnis.name,
    )


def lade_alle_reisen(reisen_pfad: Path) -> list[Reise]:
    reisen = []
    if not reisen_pfad.exists():
        return reisen
    for unterverz in sorted(reisen_pfad.iterdir()):
        if unterverz.is_dir() and (unterverz / "reise.yaml").exists():
            reisen.append(lade_reise(unterverz))
    return reisen
