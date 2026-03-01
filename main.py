#!/usr/bin/env python3
"""Reisetagebuch – Haupteinstiegspunkt.

Verwendung:
    python main.py validate [reise-verzeichnis]
    python main.py build
"""

import sys
from pathlib import Path

from reisetagebuch.loader import ValidationFehler, lade_alle_reisen, lade_reise
from reisetagebuch.generator import generiere_website

REISEN_PFAD = Path("reisen")
AUSGABE_PFAD = Path("ausgabe")
VORLAGEN_PFAD = Path("vorlagen")
STATISCH_PFAD = Path("statisch")


def cmd_validate(args: list[str]) -> int:
    if args:
        # Einzelne Reise validieren
        verz = Path(args[0])
        if not verz.exists():
            # Auch als Kurzname unter reisen/ suchen
            verz = REISEN_PFAD / args[0]
        verzeichnisse = [verz]
    else:
        # Alle Reisen validieren
        verzeichnisse = sorted(
            v for v in REISEN_PFAD.iterdir()
            if v.is_dir() and (v / "reise.yaml").exists()
        ) if REISEN_PFAD.exists() else []

    if not verzeichnisse:
        print("Keine Reisen gefunden.")
        return 0

    fehler_gesamt = 0
    for verz in verzeichnisse:
        try:
            reise = lade_reise(verz)
            print(f"\nReise: {reise.titel} ({reise.slug})")
            print(f"  Zeitraum:  {reise.anreise.datum} → {reise.abreise.datum}  ({reise.gesamttage} Tage)")
            print(f"  Etappen:   {len(reise.etappen)}")
            print()
            for i, e in enumerate(reise.etappen, 1):
                transport_ab = f" → {e.verkehrsmittel_weiter}" if e.verkehrsmittel_weiter else ""
                print(f"  {i}. {e.ort:<15} {e.ankunft}–{e.abreise}  {e.naechte} Nacht/Nächte{transport_ab}")
                if e.unterkunft:
                    print(f"       Unterkunft: {e.unterkunft}")
                if e.notizen:
                    print(f"       Notizen:    {e.notizen}")
            print(f"\n  Gesamt: {reise.gesamtnaechte} Übernachtungen")
            print("  OK – Keine Fehler gefunden.")
        except ValidationFehler as ex:
            print(f"\nFEHLER in {verz}: {ex}", file=sys.stderr)
            fehler_gesamt += 1
        except Exception as ex:
            print(f"\nUnerwarteter Fehler in {verz}: {ex}", file=sys.stderr)
            fehler_gesamt += 1

    return 1 if fehler_gesamt else 0


def cmd_build() -> int:
    reisen = lade_alle_reisen(REISEN_PFAD)
    if not reisen:
        print("Keine Reisen gefunden. Abbruch.")
        return 1

    generiere_website(
        reisen=reisen,
        ausgabe_pfad=AUSGABE_PFAD,
        vorlagen_pfad=VORLAGEN_PFAD,
        statisch_pfad=STATISCH_PFAD,
    )
    print(f"\nWebsite erfolgreich erzeugt in: {AUSGABE_PFAD}/")
    print("Lokal ansehen: python3 -m http.server 8000 --directory ausgabe/")
    return 0


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(0)

    befehl = args[0]
    rest = args[1:]

    if befehl == "validate":
        sys.exit(cmd_validate(rest))
    elif befehl == "build":
        sys.exit(cmd_build())
    else:
        print(f"Unbekannter Befehl: {befehl!r}", file=sys.stderr)
        print("Verfügbare Befehle: validate, build")
        sys.exit(1)


if __name__ == "__main__":
    main()
