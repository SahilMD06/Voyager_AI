"""Open-Meteo integration: geocoding, live forecast and historical fallback.

Rules this module follows:
* Coordinates always come from the Open-Meteo geocoding API.
* Days inside the forecast horizon (today .. today+15) use the live forecast.
* Days beyond the horizon use the *actual recorded* weather for the same
  calendar dates one year earlier (Open-Meteo archive), labelled
  ``historical`` so the UI never presents it as a forecast.
* If neither is available the day is returned as ``unavailable``.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import Counter
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.config import get_settings
from app.models.schemas import WeatherDay, WeatherResult
from app.utils.http import ExternalAPIError, get_json

logger = logging.getLogger(__name__)

FORECAST_HORIZON_DAYS = 15

# Some dataset city names do not geocode well on their own.
GEOCODE_QUERY_ALIASES = {
    "bangalore": "Bengaluru",
    "goa": "Panjim",
}

# WMO weather interpretation codes -> (label, icon key)
WMO_CODES: dict[int, tuple[str, str]] = {
    0: ("Clear sky", "sun"),
    1: ("Mainly clear", "sun"),
    2: ("Partly cloudy", "cloud-sun"),
    3: ("Overcast", "cloud"),
    45: ("Fog", "fog"),
    48: ("Depositing rime fog", "fog"),
    51: ("Light drizzle", "drizzle"),
    53: ("Moderate drizzle", "drizzle"),
    55: ("Dense drizzle", "drizzle"),
    56: ("Freezing drizzle", "drizzle"),
    57: ("Dense freezing drizzle", "drizzle"),
    61: ("Slight rain", "rain"),
    63: ("Moderate rain", "rain"),
    65: ("Heavy rain", "rain"),
    66: ("Freezing rain", "rain"),
    67: ("Heavy freezing rain", "rain"),
    71: ("Slight snowfall", "snow"),
    73: ("Moderate snowfall", "snow"),
    75: ("Heavy snowfall", "snow"),
    77: ("Snow grains", "snow"),
    80: ("Slight rain showers", "rain"),
    81: ("Moderate rain showers", "rain"),
    82: ("Violent rain showers", "rain"),
    85: ("Slight snow showers", "snow"),
    86: ("Heavy snow showers", "snow"),
    95: ("Thunderstorm", "storm"),
    96: ("Thunderstorm with slight hail", "storm"),
    99: ("Thunderstorm with heavy hail", "storm"),
}

_CACHE: dict[str, tuple[float, object]] = {}
_CACHE_LOCK = threading.Lock()
_CACHE_TTL_SECONDS = 30 * 60


def _cached(key: str):
    with _CACHE_LOCK:
        hit = _CACHE.get(key)
        if hit and time.time() - hit[0] < _CACHE_TTL_SECONDS:
            return hit[1]
    return None


def _store(key: str, value: object) -> None:
    with _CACHE_LOCK:
        _CACHE[key] = (time.time(), value)


def describe_code(code: int | None) -> tuple[str, str]:
    """Translate a WMO weather code into a label and icon key."""
    if code is None:
        return ("Unknown", "unknown")
    return WMO_CODES.get(int(code), (f"Weather code {code}", "cloud"))


def geocode_city(city: str, country_code: str = "IN") -> dict | None:
    """Resolve a city to coordinates using the Open-Meteo geocoding API.

    Returns ``None`` when no match is found (never guesses coordinates).
    """
    cache_key = f"geo:{city.lower()}:{country_code}"
    cached = _cached(cache_key)
    if cached is not None:
        return cached or None

    settings = get_settings()
    queries = [GEOCODE_QUERY_ALIASES.get(city.lower(), city)]
    if queries[0] != city:
        queries.append(city)

    for query in queries:
        params = {"name": query, "count": 10, "language": "en",
                  "format": "json"}
        if country_code:
            params["countryCode"] = country_code
        payload = get_json(settings.open_meteo_geocoding_url, params)
        results = payload.get("results") or []
        if not results:
            continue
        # Prefer administrative centres, then the most populous match.
        results.sort(
            key=lambda r: (
                r.get("feature_code") in {"PPLC", "PPLA", "PPLA2"},
                r.get("population") or 0,
            ),
            reverse=True,
        )
        best = results[0]
        location = {
            "name": best.get("name"),
            "admin1": best.get("admin1"),
            "country": best.get("country"),
            "latitude": float(best["latitude"]),
            "longitude": float(best["longitude"]),
            "timezone": best.get("timezone"),
            "query": query,
        }
        _store(cache_key, location)
        return location

    _store(cache_key, {})
    return None


def _daily_rows(payload: dict) -> dict[str, dict]:
    daily = payload.get("daily") or {}
    times = daily.get("time") or []
    rows: dict[str, dict] = {}
    for index, day in enumerate(times):
        rows[day] = {
            key: (values[index] if index < len(values) else None)
            for key, values in daily.items()
            if key != "time" and isinstance(values, list)
        }
    return rows


def _fetch_forecast(lat: float, lon: float, start: date, end: date) -> dict:
    settings = get_settings()
    key = f"fc:{lat:.3f}:{lon:.3f}:{start}:{end}"
    cached = _cached(key)
    if cached is not None:
        return cached
    payload = get_json(
        settings.open_meteo_forecast_url,
        {
            "latitude": lat,
            "longitude": lon,
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,"
                     "precipitation_probability_max,precipitation_sum",
            "timezone": "auto",
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        },
    )
    rows = _daily_rows(payload)
    _store(key, rows)
    return rows


def _fetch_archive(lat: float, lon: float, start: date, end: date) -> dict:
    """Recorded daily weather; tries the ERA5 archive, then the
    historical-forecast archive (both are real observations/analyses)."""
    settings = get_settings()
    key = f"ar:{lat:.3f}:{lon:.3f}:{start}:{end}"
    cached = _cached(key)
    if cached is not None:
        return cached
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,"
                 "precipitation_sum",
        "timezone": "auto",
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
    }
    errors = []
    for url in (settings.open_meteo_archive_url,
                settings.open_meteo_historical_forecast_url):
        try:
            rows = _daily_rows(get_json(url, params))
        except ExternalAPIError as exc:
            errors.append(str(exc))
            continue
        _store(key, rows)
        return rows
    raise ExternalAPIError("; ".join(errors))


MET_SYMBOLS: list[tuple[str, tuple[str, str]]] = [
    ("thunder", ("Thunderstorm", "storm")),
    ("snow", ("Snow", "snow")),
    ("sleet", ("Sleet", "snow")),
    ("heavyrain", ("Heavy rain", "rain")),
    ("lightrain", ("Light rain", "drizzle")),
    ("rain", ("Rain", "rain")),
    ("fog", ("Fog", "fog")),
    ("partlycloudy", ("Partly cloudy", "cloud-sun")),
    ("cloudy", ("Overcast", "cloud")),
    ("fair", ("Mainly clear", "sun")),
    ("clearsky", ("Clear sky", "sun")),
]


def describe_met_symbol(symbol: str | None) -> tuple[str, str]:
    """Translate a MET Norway symbol_code (e.g. 'lightrain_day')."""
    if not symbol:
        return ("Unknown", "unknown")
    base = symbol.split("_")[0]
    for key, value in MET_SYMBOLS:
        if key in base:
            return value
    return (base.title(), "cloud")


def _fetch_met_norway(lat: float, lon: float, tz_name: str | None) -> dict:
    """Daily aggregates from MET Norway's hourly/6-hourly forecast."""
    settings = get_settings()
    key = f"met:{lat:.3f}:{lon:.3f}"
    cached = _cached(key)
    if cached is not None:
        return cached
    payload = get_json(settings.met_norway_url,
                       {"lat": round(lat, 4), "lon": round(lon, 4)})
    zone = ZoneInfo(tz_name) if tz_name else ZoneInfo("Asia/Kolkata")
    days: dict[str, dict] = {}
    for entry in payload.get("properties", {}).get("timeseries", []):
        moment = datetime.fromisoformat(entry["time"].replace("Z", "+00:00"))
        local_day = moment.astimezone(zone).date().isoformat()
        data = entry.get("data", {})
        bucket = days.setdefault(local_day, {"temps": [], "precip": 0.0,
                                             "symbols": Counter()})
        temp = data.get("instant", {}).get("details", {}).get(
            "air_temperature")
        if temp is not None:
            bucket["temps"].append(float(temp))
        nxt = data.get("next_1_hours") or data.get("next_6_hours") or {}
        bucket["precip"] += float(
            nxt.get("details", {}).get("precipitation_amount") or 0)
        symbol = nxt.get("summary", {}).get("symbol_code")
        if symbol:
            bucket["symbols"][symbol.split("_")[0]] += 1
    rows = {}
    for day, bucket in days.items():
        if len(bucket["temps"]) < 2:
            continue  # too few readings to describe the day honestly
        rows[day] = {
            "temperature_2m_max": max(bucket["temps"]),
            "temperature_2m_min": min(bucket["temps"]),
            "precipitation_sum": round(bucket["precip"], 1),
            "symbol": (bucket["symbols"].most_common(1)[0][0]
                       if bucket["symbols"] else None),
        }
    _store(key, rows)
    return rows


def _one_year_earlier(day: date) -> date:
    try:
        return day.replace(year=day.year - 1)
    except ValueError:  # 29 Feb
        return day.replace(year=day.year - 1, day=28)


def _round(value) -> float | None:
    return round(float(value), 1) if value is not None else None


def get_trip_weather(
    city: str, start: date, end: date, today: date | None = None
) -> WeatherResult:
    """Weather for every day from ``start`` to ``end`` (inclusive)."""
    today = today or date.today()
    trip_days = [
        start + timedelta(days=i) for i in range((end - start).days + 1)
    ]

    try:
        location = geocode_city(city)
    except ExternalAPIError as exc:
        logger.error("Geocoding failed for %s: %s", city, exc)
        return WeatherResult(
            city=city, resolved_location=None, latitude=None, longitude=None,
            timezone=None, days=[_unavailable(d, "Geocoding service "
                                              "unavailable") for d in trip_days],
            note=f"Could not resolve {city}: {exc}",
        )
    if not location:
        return WeatherResult(
            city=city, resolved_location=None, latitude=None, longitude=None,
            timezone=None,
            days=[_unavailable(d, "Location not found") for d in trip_days],
            note=f"Open-Meteo could not geocode '{city}'.",
        )

    lat, lon = location["latitude"], location["longitude"]
    horizon = today + timedelta(days=FORECAST_HORIZON_DAYS)
    forecast_days = [d for d in trip_days if today <= d <= horizon]
    archive_days = [d for d in trip_days if d not in forecast_days]
    notes: list[str] = []

    forecast_rows: dict = {}
    met_rows: dict = {}
    if forecast_days:
        try:
            forecast_rows = _fetch_forecast(
                lat, lon, forecast_days[0], forecast_days[-1]
            )
        except ExternalAPIError as exc:
            logger.warning("Open-Meteo forecast failed: %s", exc)
            try:
                met_rows = _fetch_met_norway(lat, lon,
                                             location.get("timezone"))
                notes.append(
                    "Open-Meteo's free limit was reached, so forecast days "
                    "come from MET Norway (api.met.no).")
            except ExternalAPIError as met_exc:
                notes.append(f"Live forecast unavailable ({exc}; MET Norway:"
                             f" {met_exc}).")
            archive_days = [d for d in trip_days
                            if d.isoformat() not in met_rows]

    archive_rows: dict = {}
    if archive_days:
        shifted = [_one_year_earlier(d) for d in archive_days]
        try:
            archive_rows = _fetch_archive(lat, lon, min(shifted), max(shifted))
            notes.append(
                "Dates beyond Open-Meteo's 16-day forecast window show the "
                "actual weather recorded on the same dates last year "
                "(historical reference, not a forecast)."
            )
        except ExternalAPIError as exc:
            notes.append(f"Historical weather unavailable ({exc}).")

    days: list[WeatherDay] = []
    for trip_day in trip_days:
        row = forecast_rows.get(trip_day.isoformat())
        if row and row.get("temperature_2m_max") is not None:
            label, icon = describe_code(row.get("weather_code"))
            days.append(WeatherDay(
                date=trip_day, condition=label, icon=icon,
                weather_code=row.get("weather_code"),
                temp_max_c=_round(row.get("temperature_2m_max")),
                temp_min_c=_round(row.get("temperature_2m_min")),
                precipitation_probability=row.get(
                    "precipitation_probability_max"),
                precipitation_mm=_round(row.get("precipitation_sum")),
                source="forecast",
                source_note="Open-Meteo live forecast",
            ))
            continue
        row = met_rows.get(trip_day.isoformat())
        if row:
            label, icon = describe_met_symbol(row.get("symbol"))
            days.append(WeatherDay(
                date=trip_day, condition=label, icon=icon, weather_code=None,
                temp_max_c=_round(row["temperature_2m_max"]),
                temp_min_c=_round(row["temperature_2m_min"]),
                precipitation_probability=None,
                precipitation_mm=_round(row.get("precipitation_sum")),
                source="forecast",
                source_note="MET Norway forecast (Open-Meteo limit reached)",
            ))
            continue
        ref = _one_year_earlier(trip_day)
        row = archive_rows.get(ref.isoformat())
        if row and row.get("temperature_2m_max") is not None:
            label, icon = describe_code(row.get("weather_code"))
            days.append(WeatherDay(
                date=trip_day, condition=label, icon=icon,
                weather_code=row.get("weather_code"),
                temp_max_c=_round(row.get("temperature_2m_max")),
                temp_min_c=_round(row.get("temperature_2m_min")),
                precipitation_probability=None,
                precipitation_mm=_round(row.get("precipitation_sum")),
                source="historical",
                source_note=f"Recorded on {ref.isoformat()} (Open-Meteo "
                            "archive)",
            ))
            continue
        days.append(_unavailable(trip_day, "No forecast or historical data"))

    resolved = ", ".join(
        p for p in (location.get("name"), location.get("admin1")) if p
    )
    return WeatherResult(
        city=city, resolved_location=resolved, latitude=lat, longitude=lon,
        timezone=location.get("timezone"), days=days, note=" ".join(notes),
    )


def _unavailable(day: date, reason: str) -> WeatherDay:
    return WeatherDay(
        date=day, condition="Unavailable", icon="unknown", weather_code=None,
        temp_max_c=None, temp_min_c=None, source="unavailable",
        source_note=reason,
    )
