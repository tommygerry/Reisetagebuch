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

    def __post_init__(self):
        self.abreise = self.ankunft + timedelta(days=self.naechte)


@dataclass
class Tageseintrag:
    datum: date
    titel: str
    ort: str
    inhalt_html: str           # gerendertes Markdown
    wetter: str = ""
    stimmung: str = ""         # z.B. "😊", "müde", "aufgeregt"
    slug: str = ""             # YYYY-MM-DD, wird vom Loader gesetzt


@dataclass
class Reise:
    titel: str
    beschreibung: str
    anreise: Anreise
    abreise: Abreise
    etappen: list[Etappe] = field(default_factory=list)
    eintraege: list[Tageseintrag] = field(default_factory=list)
    deckbild: str = ""
    slug: str = ""             # Verzeichnisname, wird vom Loader gesetzt

    @property
    def gesamtnaechte(self) -> int:
        return (self.abreise.datum - self.anreise.datum).days

    @property
    def gesamttage(self) -> int:
        return self.gesamtnaechte + 1
