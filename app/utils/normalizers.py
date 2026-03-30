"""
Funções de normalização aplicadas após a extração por regex.
Referenciadas pelo nome (string) nas regras do banco.
"""
import re
from datetime import datetime


def strip(value: str) -> str:
    return value.strip()


def digits_only(value: str) -> str:
    return re.sub(r"\D", "", value)


def date_iso(value: str) -> str:
    """Converte DD/MM/YYYY ou DD-MM-YYYY para YYYY-MM-DD."""
    value = value.strip()
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return value  # retorna original se não conseguir converter


def currency_brl(value: str) -> str:
    """Normaliza valor monetário BR para string decimal: '1.250,50' → '1250.50'"""
    value = value.strip().replace("R$", "").strip()
    # Remove pontos de milhar, troca vírgula decimal por ponto
    value = re.sub(r"\.", "", value)
    value = value.replace(",", ".")
    try:
        return str(float(value))
    except ValueError:
        return value


NORMALIZERS: dict[str, callable] = {
    "strip": strip,
    "digits_only": digits_only,
    "date_iso": date_iso,
    "currency_brl": currency_brl,
    "none": lambda x: x,
}


def apply(normalizer_name: str, value: str) -> str:
    fn = NORMALIZERS.get(normalizer_name, strip)
    return fn(value)
