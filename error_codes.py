"""Codici errore e eccezione strutturata per MyNotes."""

from __future__ import annotations

ERROR_CODES: dict[str, str] = {
    # Updater
    "UPD-001": "Impossibile contattare GitHub (errore di rete)",
    "UPD-002": "Risposta API GitHub non valida",
    "UPD-003": "Nessun asset per questa piattaforma",
    "UPD-004": "Download aggiornamento fallito",
    "UPD-005": "Estrazione archivio fallita",
    "UPD-006": "Applicazione file aggiornamento fallita",
    "UPD-007": "Creazione script aggiornamento Windows fallita",
    # Backup
    "BKP-001": "Errore backup locale",
    "BKP-002": "Errore connessione Google Drive",
    "BKP-003": "Ripristino backup fallito",
    "BKP-004": "Verifica integrita' backup fallita",
    "BKP-005": "Crittografia backup fallita",
    "BKP-006": "Decrittografia backup fallita",
    "BKP-007": "Scheduler backup fallito",
    # Export (predisposti)
    "EXP-001": "Errore esportazione nota",
    "EXP-002": "Errore importazione nota",
}


def get_error_message(code: str) -> str:
    """Ritorna la descrizione italiana per un codice errore."""
    return ERROR_CODES.get(code, "Errore sconosciuto")


class AppError(Exception):
    """Eccezione con codice errore strutturato.

    Attributes:
        code: Codice errore (es. "UPD-001")
        message: Descrizione leggibile (da ERROR_CODES)
        detail: Dettaglio tecnico (es. str dell'eccezione originale)
    """

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.message = get_error_message(code)
        self.detail = detail
        super().__init__(str(self))

    def __str__(self) -> str:
        s = f"[{self.code}] {self.message}"
        if self.detail:
            s += f": {self.detail}"
        return s
