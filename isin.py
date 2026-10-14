"""Nettoyage et validation des codes ISIN (norme ISO 6166)."""
import re

_FORMAT = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")


def normaliser(code) -> str:
    """Met en majuscules et retire espaces, tirets et points."""
    return re.sub(r"[\s\-\.]", "", str(code or "")).upper()


def est_valide(isin: str) -> bool:
    """Vérifie le format et la clé de contrôle (algorithme de Luhn)."""
    if not _FORMAT.match(isin):
        return False
    chiffres = "".join(str(int(c, 36)) for c in isin[:-1])
    total = 0
    for i, c in enumerate(reversed(chiffres)):
        n = int(c)
        if i % 2 == 0:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return (10 - total % 10) % 10 == int(isin[-1])


def extraire(texte: str) -> list[str]:
    """Découpe un copier-coller (lignes, virgules, points-virgules, tabulations)."""
    morceaux = re.split(r"[\n,;\t]+", texte or "")
    return [normaliser(m) for m in morceaux if normaliser(m)]
