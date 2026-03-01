from datetime import date, timedelta
from pathlib import Path

import yaml

from .models import Anreise, Abreise, Etappe, Reise


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

        # Wenn abreise explizit angegeben: gegen naechte prüfen
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

        # Lückenfreiheit prüfen
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

    # Anreise
    anreise_roh = d.get("anreise")
    if not anreise_roh or "datum" not in anreise_roh:
        raise ValidationFehler("'anreise.datum' fehlt")
    anreise = Anreise(
        datum=_als_datum(anreise_roh["datum"], "anreise.datum"),
        von=anreise_roh.get("von", ""),
        verkehrsmittel=anreise_roh.get("verkehrsmittel", ""),
    )

    # Abreise
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

    # Etappen
    etappen_roh = d.get("etappen", [])
    if not etappen_roh:
        raise ValidationFehler("Mindestens eine Etappe muss definiert sein")

    etappen = _parse_etappen(etappen_roh, anreise.datum)

    # Letzte Etappe muss am Abreisedatum enden
    if etappen[-1].abreise != abreise.datum:
        raise ValidationFehler(
            f"Letzte Etappe ({etappen[-1].ort}): Ende ({etappen[-1].abreise}) muss dem "
            f"Abreisedatum ({abreise.datum}) entsprechen"
        )

    # Übernachtungssumme prüfen
    summe = sum(e.naechte for e in etappen)
    gesamt = (abreise.datum - anreise.datum).days
    if summe != gesamt:
        raise ValidationFehler(
            f"Summe der Übernachtungen ({summe}) ≠ Gesamtdauer ({gesamt} Nächte)"
        )

    return Reise(
        titel=titel,
        beschreibung=d.get("beschreibung", ""),
        anreise=anreise,
        abreise=abreise,
        etappen=etappen,
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
