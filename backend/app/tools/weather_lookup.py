"""Tool 4 - Weather lookup (Open-Meteo)."""

from __future__ import annotations

from datetime import date

from app.models.schemas import WeatherResult
from app.services.weather_service import get_trip_weather


def lookup_weather(city: str, start_date: date, end_date: date) -> WeatherResult:
    """Daily weather for ``city`` across the trip dates.

    Uses the live forecast where Open-Meteo has one and real historical
    observations (same dates last year) otherwise. Never invents values.
    """
    if end_date < start_date:
        start_date, end_date = end_date, start_date
    return get_trip_weather(city, start_date, end_date)
