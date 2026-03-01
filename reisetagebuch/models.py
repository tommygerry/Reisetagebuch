from dataclasses import dataclass, field
from datetime import date, timedelta


@dataclass
class Anreise:
    datum: date
    von: str = ""
    verkehrsmittel: str = ""


@dataclass
class Abreise:
    datum: date
    nach: str = ""
    verkehrsmittel: str = ""


@dataclass
class Foto:
    dateiname: str              # z.B. "2026-06-01_kolosseum.jpg"
    pfad_relativ: str           # z.B. "fotos/2026-06-01_kolosseum.jpg" (relativ zur Reise-Ausgabe)
    datum: date | None = None   # aus EXIF DateTimeOriginal oder Dateinamen-Präfix
    lat: float | None = None    # aus EXIF GPS (Dezimalgrad)
    lon: float | None = None    # aus EXIF GPS (Dezimalgrad)
    beschriftung: str = ""
    alt: str = ""               # Alternativtext; fallback = beschriftung oder dateiname
    datum_quelle: str = ""      # "exif" | "dateiname" | ""


@dataclass
class Etappe:
    ort: str
    lat: float
    lon: float
    ankunft: date
    naechte: int
    abreise: date = field(init=False)
    unterkunft: str = ""
    verkehrsmittel_weiter: str = ""
    notizen: str = ""
    fotos: list["Foto"] = field(default_factory=list)   # wird vom Loader befüllt

    def __post_init__(self):
        self.abreise = self.ankunft + timedelta(days=self.naechte)


@dataclass
class Tageseintrag:
    datum: date
    titel: str
    ort: str
    inhalt_html: str           # gerendertes Markdown
    wetter: str = ""
    stimmung: str = ""
    slug: str = ""             # YYYY-MM-DD
    fotos: list[Foto] = field(default_factory=list)   # Fotos dieses Tages


@dataclass
class Reise:
    titel: str
    beschreibung: str
    anreise: Anreise
    abreise: Abreise
    etappen: list[Etappe] = field(default_factory=list)
    eintraege: list[Tageseintrag] = field(default_factory=list)
    fotos: list[Foto] = field(default_factory=list)    # alle Fotos der Reise
    deckbild: str = ""
    slug: str = ""

    @property
    def gesamtnaechte(self) -> int:
        return (self.abreise.datum - self.anreise.datum).days

    @property
    def gesamttage(self) -> int:
        return self.gesamtnaechte + 1
