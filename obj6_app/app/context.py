import time
from datetime import datetime
import httpx
from hijridate import Gregorian
from .features import Context, FORMALITY

CITIES = {"tunis": (36.81, 10.18), "sfax": (34.74, 10.76), "sousse": (35.83, 10.64), "bizerte": (37.27, 9.87),
 "nabeul": (36.45, 10.73), "gabès": (33.88, 10.10), "kairouan": (35.68, 10.10), "monastir": (35.78, 10.83),
 "djerba": (33.81, 10.85), "tozeur": (33.92, 8.13)}

_W = {}

async def get_weather(city: str):
    k = city.lower()
    if k in _W and time.time() - _W[k][0] < 600: return _W[k][1]
    lat, lon = CITIES.get(k, CITIES["tunis"])
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get("https://api.open-meteo.com/v1/forecast", params={"latitude": lat, "longitude": lon,
                "current": "apparent_temperature,wind_speed_10m", "daily": "precipitation_probability_max",
                "timezone": "auto", "forecast_days": 1})
            r.raise_for_status(); j = r.json()
        res = {"feels_like": j["current"]["apparent_temperature"], "wind": j["current"]["wind_speed_10m"],
                "rain_prob": (j["daily"]["precipitation_probability_max"][0] or 0) / 100, "source": "open-meteo"}
        _W[k] = (time.time(), res); return res
    except Exception:
        return {"feels_like": 20.0, "wind": 10.0, "rain_prob": 0.0, "source": "default (météo indisponible)"}

def build_context(now: datetime, wx: dict, occasion=None, formality=None) -> Context:
    h = Gregorian(now.year, now.month, now.day).to_hijri()
    ramadan = int(h.month == 9)
    eid = int((h.month == 10 and h.day <= 3) or (h.month == 12 and 10 <= h.day <= 13))
    if occasion is None:
        occasion = "religious" if eid else ("work" if now.weekday() < 5 else "casual")
    return Context(wx["feels_like"], wx["rain_prob"], wx["wind"], occasion,
                   FORMALITY[occasion] if formality is None else formality, now.hour, ramadan, eid)
