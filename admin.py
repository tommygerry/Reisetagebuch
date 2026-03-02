"""
Reisetagebuch Admin – lokales Web-Interface
Starten: python admin.py
Öffnet automatisch http://localhost:5001
"""
import subprocess
import sys
from datetime import date
from pathlib import Path

import yaml
from flask import Flask, flash, jsonify, redirect, render_template, request, send_from_directory, url_for

app = Flask(__name__, template_folder="vorlagen_admin")
app.secret_key = "reisetagebuch-admin-lokal-2026"

REISEN_PFAD = Path("reisen")
BILD_ENDUNGEN = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif", ".tiff"}


# ── Dateisystem-Helfer ────────────────────────────────────────────────

def _lade_yaml(pfad: Path) -> dict:
    if not pfad.exists():
        return {}
    with pfad.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _speichere_yaml(pfad: Path, daten: dict) -> None:
    with pfad.open("w", encoding="utf-8") as f:
        yaml.dump(daten, f, allow_unicode=True, sort_keys=False, default_flow_style=False)


def _alle_reisen() -> list[dict]:
    if not REISEN_PFAD.exists():
        return []
    reisen = []
    for p in sorted(REISEN_PFAD.iterdir()):
        if p.is_dir() and (p / "reise.yaml").exists():
            d = _lade_yaml(p / "reise.yaml")
            anreise = d.get("anreise", {})
            abreise = d.get("abreise", {})
            reisen.append({
                "slug": p.name,
                "titel": d.get("titel", p.name),
                "anreise_datum": anreise.get("datum", ""),
                "abreise_datum": abreise.get("datum", ""),
                "etappen_anzahl": len(d.get("etappen", [])),
            })
    return reisen


def _daten_fuer_formular(daten: dict) -> dict:
    """Konvertiert date-Objekte in ISO-Strings für HTML-Formularfelder."""
    import copy
    from datetime import date as Date
    d = copy.deepcopy(daten)
    for schluessel in ("anreise", "abreise"):
        abschnitt = d.get(schluessel, {})
        if isinstance(abschnitt.get("datum"), Date):
            abschnitt["datum"] = abschnitt["datum"].isoformat()
    for e in d.get("etappen", []):
        for feld in ("ankunft", "abreise"):
            if isinstance(e.get(feld), Date):
                e[feld] = e[feld].isoformat()
    return d


def _sicherer_slug(s: str) -> str:
    """Erlaubt nur Buchstaben, Ziffern und Bindestriche."""
    import re
    return re.sub(r"[^a-z0-9\-]", "", s.lower().replace(" ", "-"))[:80]


def _form_zu_reise_dict(form) -> dict:
    daten: dict = {
        "titel": form.get("titel", "").strip(),
        "beschreibung": form.get("beschreibung", "").strip(),
        "anreise": {
            "datum": form.get("anreise_datum", ""),
            "von": form.get("anreise_von", "").strip(),
            "verkehrsmittel": form.get("anreise_vm", "").strip(),
        },
        "abreise": {
            "datum": form.get("abreise_datum", ""),
            "nach": form.get("abreise_nach", "").strip(),
            "verkehrsmittel": form.get("abreise_vm", "").strip(),
        },
        "etappen": _etappen_aus_formular(form),
    }
    if form.get("deckbild", "").strip():
        daten["deckbild"] = form["deckbild"].strip()
    return daten


def _etappen_aus_formular(form) -> list[dict]:
    etappen = []
    i = 0
    while f"etappe_{i}_ort" in form:
        ort = form.get(f"etappe_{i}_ort", "").strip()
        if ort:
            e: dict = {"ort": ort}
            try:
                e["lat"] = float(form[f"etappe_{i}_lat"])
                e["lon"] = float(form[f"etappe_{i}_lon"])
            except (KeyError, ValueError):
                e["lat"] = 0.0
                e["lon"] = 0.0
            e["ankunft"] = form.get(f"etappe_{i}_ankunft", "")
            try:
                e["naechte"] = int(form[f"etappe_{i}_naechte"])
            except (KeyError, ValueError):
                e["naechte"] = 1
            for opt in ("unterkunft", "verkehrsmittel_weiter", "notizen"):
                val = form.get(f"etappe_{i}_{opt}", "").strip()
                if val:
                    e[opt] = val
            etappen.append(e)
        i += 1
    return etappen


def _schreibe_eintrag(pfad: Path, titel: str, ort: str,
                       wetter: str, stimmung: str, inhalt: str) -> None:
    fm: list[str] = ["---"]
    if titel:
        fm.append(f'titel: "{titel}"')
    if ort:
        fm.append(f'ort: "{ort}"')
    if wetter:
        fm.append(f'wetter: "{wetter}"')
    if stimmung:
        fm.append(f'stimmung: "{stimmung}"')
    fm.append("---\n")
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text("\n".join(fm) + "\n" + inhalt, encoding="utf-8")


def _lese_eintrag(pfad: Path) -> dict:
    if not pfad.exists():
        return {}
    text = pfad.read_text(encoding="utf-8")
    if text.startswith("---"):
        teile = text.split("---", 2)
        if len(teile) >= 3:
            try:
                fm = yaml.safe_load(teile[1]) or {}
                return {**fm, "inhalt": teile[2].lstrip("\n")}
            except yaml.YAMLError:
                pass
    return {"inhalt": text}


# ── Git & Build ───────────────────────────────────────────────────────

def _git(args: list[str]) -> tuple[int, str]:
    r = subprocess.run(["git"] + args, capture_output=True, text=True, encoding="utf-8")
    return r.returncode, (r.stdout + r.stderr).strip()


def _run(cmd: list[str]) -> tuple[int, str]:
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    return r.returncode, (r.stdout + r.stderr).strip()


# ── Routen: Dashboard ─────────────────────────────────────────────────

@app.route("/")
def startseite():
    return render_template("startseite.html", reisen=_alle_reisen())


# ── Routen: Reise anlegen / bearbeiten ───────────────────────────────

@app.route("/reisen/neu", methods=["GET", "POST"])
def reise_neu():
    if request.method == "POST":
        slug = _sicherer_slug(request.form.get("slug", ""))
        if not slug:
            flash("Ungültiger Verzeichnisname (Slug).", "danger")
            return render_template("reise_form.html", reise=request.form, neu=True)
        reise_pfad = REISEN_PFAD / slug
        if reise_pfad.exists():
            flash(f"Reise '{slug}' existiert bereits.", "danger")
            return render_template("reise_form.html", reise=request.form, neu=True)
        reise_pfad.mkdir(parents=True)
        (reise_pfad / "tage").mkdir()
        (reise_pfad / "fotos").mkdir()
        _speichere_yaml(reise_pfad / "reise.yaml", _form_zu_reise_dict(request.form))
        flash(f"Reise '{slug}' wurde angelegt.", "success")
        return redirect(url_for("reise_detail", slug=slug))
    return render_template("reise_form.html", reise={}, neu=True)


@app.route("/reisen/<slug>")
def reise_detail(slug):
    slug = _sicherer_slug(slug)
    reise_pfad = REISEN_PFAD / slug
    if not reise_pfad.exists():
        flash("Reise nicht gefunden.", "danger")
        return redirect(url_for("startseite"))
    daten = _lade_yaml(reise_pfad / "reise.yaml")
    eintraege = []
    if (reise_pfad / "tage").exists():
        for f in sorted((reise_pfad / "tage").glob("*.md")):
            eintraege.append(f.stem)
    fotos = []
    if (reise_pfad / "fotos").exists():
        for f in sorted((reise_pfad / "fotos").iterdir()):
            if f.suffix.lower() in BILD_ENDUNGEN:
                fotos.append(f.name)
    return render_template("reise_detail.html", slug=slug, daten=daten,
                           eintraege=eintraege, fotos=fotos)


@app.route("/reisen/<slug>/bearbeiten", methods=["GET", "POST"])
def reise_bearbeiten(slug):
    slug = _sicherer_slug(slug)
    reise_pfad = REISEN_PFAD / slug
    if not reise_pfad.exists():
        return redirect(url_for("startseite"))
    if request.method == "POST":
        _speichere_yaml(reise_pfad / "reise.yaml", _form_zu_reise_dict(request.form))
        flash("Reisedaten gespeichert.", "success")
        return redirect(url_for("reise_detail", slug=slug))
    daten = _daten_fuer_formular(_lade_yaml(reise_pfad / "reise.yaml"))
    return render_template("reise_form.html", reise=daten, slug=slug, neu=False)


# ── Routen: Tageseinträge ─────────────────────────────────────────────

@app.route("/reisen/<slug>/eintraege/neu", methods=["GET", "POST"])
def eintrag_neu(slug):
    slug = _sicherer_slug(slug)
    reise_pfad = REISEN_PFAD / slug
    if request.method == "POST":
        datum_str = request.form.get("datum", "").strip()
        if not datum_str:
            flash("Datum ist erforderlich.", "danger")
            return render_template("eintrag_form.html", slug=slug,
                                   eintrag=request.form, neu=True)
        pfad = reise_pfad / "tage" / f"{datum_str}.md"
        _schreibe_eintrag(pfad,
                          request.form.get("titel", ""),
                          request.form.get("ort", ""),
                          request.form.get("wetter", ""),
                          request.form.get("stimmung", ""),
                          request.form.get("inhalt", ""))
        flash(f"Eintrag {datum_str} gespeichert.", "success")
        return redirect(url_for("reise_detail", slug=slug))
    return render_template("eintrag_form.html", slug=slug,
                           eintrag={"datum": date.today().isoformat()}, neu=True)


@app.route("/reisen/<slug>/eintraege/<datum>/bearbeiten", methods=["GET", "POST"])
def eintrag_bearbeiten(slug, datum):
    slug = _sicherer_slug(slug)
    reise_pfad = REISEN_PFAD / slug
    pfad = reise_pfad / "tage" / f"{datum}.md"
    if request.method == "POST":
        _schreibe_eintrag(pfad,
                          request.form.get("titel", ""),
                          request.form.get("ort", ""),
                          request.form.get("wetter", ""),
                          request.form.get("stimmung", ""),
                          request.form.get("inhalt", ""))
        flash(f"Eintrag {datum} gespeichert.", "success")
        return redirect(url_for("reise_detail", slug=slug))
    eintrag = {"datum": datum, **_lese_eintrag(pfad)}
    return render_template("eintrag_form.html", slug=slug,
                           eintrag=eintrag, neu=False, datum=datum)


@app.route("/reisen/<slug>/eintraege/<datum>/loeschen", methods=["POST"])
def eintrag_loeschen(slug, datum):
    slug = _sicherer_slug(slug)
    pfad = REISEN_PFAD / slug / "tage" / f"{datum}.md"
    if pfad.exists():
        pfad.unlink()
        flash(f"Eintrag {datum} gelöscht.", "success")
    return redirect(url_for("reise_detail", slug=slug))


# ── Routen: Fotos ─────────────────────────────────────────────────────

@app.route("/reisen/<slug>/fotos", methods=["POST"])
def fotos_hochladen(slug):
    slug = _sicherer_slug(slug)
    fotos_pfad = REISEN_PFAD / slug / "fotos"
    fotos_pfad.mkdir(parents=True, exist_ok=True)
    n = 0
    for datei in request.files.getlist("fotos"):
        if datei.filename and Path(datei.filename).suffix.lower() in BILD_ENDUNGEN:
            ziel = fotos_pfad / Path(datei.filename).name
            datei.save(str(ziel))
            n += 1
    flash(f"{n} Foto(s) hochgeladen.", "success" if n else "warning")
    return redirect(url_for("reise_detail", slug=slug))


@app.route("/reisen/<slug>/fotos/<name>/loeschen", methods=["POST"])
def foto_loeschen(slug, name):
    slug = _sicherer_slug(slug)
    pfad = REISEN_PFAD / slug / "fotos" / Path(name).name
    if pfad.exists() and pfad.suffix.lower() in BILD_ENDUNGEN:
        pfad.unlink()
        flash(f"Foto '{name}' gelöscht.", "success")
    return redirect(url_for("reise_detail", slug=slug))


# ── Routen: Foto-Vorschau ─────────────────────────────────────────────

@app.route("/foto/<slug>/<name>")
def foto_anzeigen(slug, name):
    slug = _sicherer_slug(slug)
    fotos_pfad = (REISEN_PFAD / slug / "fotos").resolve()
    return send_from_directory(str(fotos_pfad), Path(name).name)


# ── API: Build & Git (JSON, für async JS) ────────────────────────────

@app.route("/api/validieren", methods=["POST"])
def api_validieren():
    code, out = _run([sys.executable, "main.py", "validate"])
    return jsonify({"ok": code == 0, "ausgabe": out})


@app.route("/api/bauen", methods=["POST"])
def api_bauen():
    code, out = _run([sys.executable, "main.py", "build"])
    return jsonify({"ok": code == 0, "ausgabe": out})


@app.route("/api/git/status", methods=["GET"])
def api_git_status():
    _, out = _git(["status", "--short"])
    _, branch = _git(["rev-parse", "--abbrev-ref", "HEAD"])
    return jsonify({"branch": branch.strip(), "status": out})


@app.route("/api/git/commit", methods=["POST"])
def api_git_commit():
    nachricht = (request.json or {}).get("nachricht", "").strip()
    if not nachricht:
        return jsonify({"ok": False, "ausgabe": "Commit-Nachricht fehlt."})
    code1, out1 = _git(["add", "reisen/"])
    if code1 != 0:
        return jsonify({"ok": False, "ausgabe": out1})
    code2, out2 = _git(["commit", "-m", nachricht])
    return jsonify({"ok": code2 == 0, "ausgabe": (out1 + "\n" + out2).strip()})


@app.route("/api/git/push", methods=["POST"])
def api_git_push():
    _, branch = _git(["rev-parse", "--abbrev-ref", "HEAD"])
    code, out = _git(["push", "-u", "origin", branch.strip()])
    return jsonify({"ok": code == 0, "ausgabe": out})


# ── Einstiegspunkt ────────────────────────────────────────────────────

if __name__ == "__main__":
    import threading
    import webbrowser
    REISEN_PFAD.mkdir(exist_ok=True)
    print("Reisetagebuch Admin  →  http://localhost:5001")
    threading.Timer(1.2, lambda: webbrowser.open("http://localhost:5001")).start()
    app.run(host="127.0.0.1", port=5001, debug=False)
