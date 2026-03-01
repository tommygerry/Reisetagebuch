import math
from datetime import date, timedelta
from pathlib import Path

import markdown
import yaml

from .models import Anreise, Abreise, Etappe, Foto, Reise, Tageseintrag

try:
    import exifread as _exifread
    _EXIF_VERFUEGBAR = True
except ImportError:
    _EXIF_VERFUEGBAR = False


class ValidationFehler(Exception):
    pass


_BILD_ENDUNGEN = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif", ".tiff", ".tif"}


# ── EXIF-Hilfsfunktionen ─────────────────────────────────────────────

def _exif_datum(tags: dict) -> date | None:
    """Liest DateTimeOriginal aus EXIF-Tags. Format: 'YYYY:MM:DD HH:MM:SS'."""
    tag = tags.get("EXIF DateTimeOriginal") or tags.get("Image DateTimeOriginal")
    if tag is None:
        return None
    try:
        teil = str(tag).split()[0]          # "YYYY:MM:DD"
        return date.fromisoformat(teil.replace(":", "-"))
    except (ValueError, IndexError):
        return None


def _rational_zu_grad(rationals) -> float:
    """Konvertiert EXIF-RATIONAL-Liste [Grad, Min, Sek] → Dezimalgrad."""
    def r2f(rational) -> float:
        # exifread liefert entweder IfdTag-Werte oder Fraction-Objekte
        try:
            return float(rational.num) / float(rational.den)
        except AttributeError:
            return float(rational)

    werte = list(rationals.values)
    if len(werte) != 3:
        return 0.0
    grad, minute, sekunde = r2f(werte[0]), r2f(werte[1]), r2f(werte[2])
    return grad + minute / 60.0 + sekunde / 3600.0


def _exif_gps(tags: dict) -> tuple[float, float] | None:
    """Liest GPS-Koordinaten aus EXIF. Gibt (lat, lon) zurück oder None."""
    lat_tag = tags.get("GPS GPSLatitude")
    lon_tag = tags.get("GPS GPSLongitude")
    lat_ref = str(tags.get("GPS GPSLatitudeRef", "N"))
    lon_ref = str(tags.get("GPS GPSLongitudeRef", "E"))

    if lat_tag is None or lon_tag is None:
        return None
    try:
        lat = _rational_zu_grad(lat_tag)
        lon = _rational_zu_grad(lon_tag)
        if "S" in lat_ref.upper():
            lat = -lat
        if "W" in lon_ref.upper():
            lon = -lon
        return lat, lon
    except Exception:
        return None


def _lese_exif(pfad: Path) -> dict:
    """Liest EXIF-Tags aus einer Bilddatei. Gibt leeres dict zurück bei Fehler."""
    if not _EXIF_VERFUEGBAR:
        return {}
    try:
        with pfad.open("rb") as f:
            return _exifread.process_file(f, details=False, stop_tag="GPS GPSLongitude")
    except Exception:
        return {}


# ── GPS-Proximity ─────────────────────────────────────────────────────

_ERDDURCHMESSER_KM = 6371.0
_MAX_ENTFERNUNG_KM = 80.0      # Fotos weiter als 80 km werden nicht zugeordnet


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Berechnet die Großkreis-Entfernung zwischen zwei Punkten in Kilometern."""
    r = _ERDDURCHMESSER_KM
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _naechste_etappe(lat: float, lon: float, etappen: list[Etappe]) -> Etappe | None:
    """Gibt die räumlich nächste Etappe zurück, wenn sie innerhalb des Schwellenwerts liegt."""
    naechste, min_dist = None, float("inf")
    for etappe in etappen:
        dist = _haversine_km(lat, lon, etappe.lat, etappe.lon)
        if dist < min_dist:
            min_dist, naechste = dist, etappe
    if naechste is not None and min_dist <= _MAX_ENTFERNUNG_KM:
        return naechste
    return None


# ── Allgemeine Helfer ─────────────────────────────────────────────────

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
    """Liest eine Markdown-Datei mit optionalem YAML-Frontmatter."""
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


# ── Fotos laden ───────────────────────────────────────────────────────

def _lade_fotos(verzeichnis: Path) -> list[Foto]:
    """Lädt alle Fotos aus reisen/<slug>/fotos/ mit EXIF und optionaler fotos.yaml."""
    fotos_pfad = verzeichnis / "fotos"
    if not fotos_pfad.exists():
        return []

    # Optionale Beschriftungen aus fotos.yaml
    meta: dict[str, dict] = {}
    yaml_pfad = fotos_pfad / "fotos.yaml"
    if yaml_pfad.exists():
        with yaml_pfad.open(encoding="utf-8") as f:
            roh = yaml.safe_load(f) or {}
        for dateiname, werte in roh.items():
            if isinstance(werte, dict):
                meta[str(dateiname)] = werte
            elif isinstance(werte, str):
                meta[str(dateiname)] = {"beschriftung": werte}

    fotos: list[Foto] = []
    for datei in sorted(fotos_pfad.iterdir()):
        if datei.suffix.lower() not in _BILD_ENDUNGEN:
            continue

        # 1. EXIF lesen
        exif_tags = _lese_exif(datei)
        exif_datum = _exif_datum(exif_tags)
        exif_gps   = _exif_gps(exif_tags)

        # 2. Datum: EXIF hat Vorrang, Fallback auf Dateinamen-Präfix
        datum: date | None = None
        datum_quelle = ""
        if exif_datum is not None:
            datum = exif_datum
            datum_quelle = "exif"
        elif len(datei.stem) >= 10 and datei.stem[4] == "-" and datei.stem[7] == "-":
            try:
                datum = date.fromisoformat(datei.stem[:10])
                datum_quelle = "dateiname"
            except ValueError:
                pass

        # 3. GPS aus EXIF
        lat = exif_gps[0] if exif_gps else None
        lon = exif_gps[1] if exif_gps else None

        info = meta.get(datei.name, {})
        beschriftung = str(info.get("beschriftung", ""))
        alt = str(info.get("alt", beschriftung or datei.stem.replace("-", " ").replace("_", " ")))

        fotos.append(Foto(
            dateiname=datei.name,
            pfad_relativ=f"fotos/{datei.name}",
            datum=datum,
            lat=lat,
            lon=lon,
            beschriftung=beschriftung,
            alt=alt,
            datum_quelle=datum_quelle,
        ))

    return fotos


def _zuordnen_fotos(fotos: list[Foto], etappen: list[Etappe], eintraege: list[Tageseintrag]) -> None:
    """
    Weist Fotos den Etappen und Tageseinträgen zu (in-place).

    Priorität:
    1. Datum (aus EXIF oder Dateiname) → Etappe nach Datumsbereich, Eintrag nach exaktem Datum
    2. GPS-Koordinaten → nächste Etappe per Haversine-Distanz (nur wenn kein Datum verfügbar)
    """
    for foto in fotos:
        etappe_gefunden = False

        # Priorität 1: Datum-basierte Zuordnung
        if foto.datum is not None:
            for etappe in etappen:
                if etappe.ankunft <= foto.datum < etappe.abreise:
                    etappe.fotos.append(foto)
                    etappe_gefunden = True
                    break
            for eintrag in eintraege:
                if eintrag.datum == foto.datum:
                    eintrag.fotos.append(foto)
                    break

        # Priorität 2: GPS-Proximity (nur wenn kein Datum gefunden)
        if not etappe_gefunden and foto.lat is not None and foto.lon is not None:
            naechste = _naechste_etappe(foto.lat, foto.lon, etappen)
            if naechste is not None:
                naechste.fotos.append(foto)


# ── Einträge und Etappen laden ────────────────────────────────────────

def _lade_eintraege(verzeichnis: Path, anreise_datum: date, abreise_datum: date) -> list[Tageseintrag]:
    tage_pfad = verzeichnis / "tage"
    if not tage_pfad.exists():
        return []

    eintraege: list[Tageseintrag] = []
    md = markdown.Markdown(extensions=["extra", "nl2br"])

    for datei in sorted(tage_pfad.glob("*.md")):
        try:
            datum = date.fromisoformat(datei.stem)
        except ValueError:
            continue

        if not (anreise_datum <= datum < abreise_datum):
            continue

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
    fotos = _lade_fotos(verzeichnis)
    _zuordnen_fotos(fotos, etappen, eintraege)

    return Reise(
        titel=titel,
        beschreibung=d.get("beschreibung", ""),
        anreise=anreise,
        abreise=abreise,
        etappen=etappen,
        eintraege=eintraege,
        fotos=fotos,
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
