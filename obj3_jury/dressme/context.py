"""Contexte de la tenue : température, pluie, occasion."""
import json
import urllib.request

from .config import TUNIS
from .schema import OCCASIONS


def make_context(temperature=None, pluie=False, occasion="décontracté"):
    if occasion not in OCCASIONS:
        raise ValueError(f"Occasion inconnue : {occasion}. Choix : {list(OCCASIONS)}")
    return {"temperature": temperature, "pluie": bool(pluie), "occasion": occasion}


def fetch_weather(lat=None, lon=None):
    """Météo actuelle via Open-Meteo (gratuit, sans clé). Par défaut : Tunis."""
    lat, lon = (lat, lon) if lat is not None else TUNIS
    url = (f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
           "&current=temperature_2m,precipitation")
    with urllib.request.urlopen(url, timeout=10) as r:
        cur = json.load(r)["current"]
    return {"temperature": cur["temperature_2m"], "pluie": cur["precipitation"] > 0}


def describe_context(ctx):
    if not ctx:
        return "aucun contexte"
    t = "température inconnue" if ctx.get("temperature") is None else f"{ctx['temperature']:g} °C"
    return f"{t}, {'pluie' if ctx.get('pluie') else 'pas de pluie'}, occasion : {ctx.get('occasion', '?')}"
