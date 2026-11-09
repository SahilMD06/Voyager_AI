"""Shared fixtures. Network calls to Open-Meteo/Wikipedia are stubbed by
default so the suite is deterministic; tests marked ``live`` hit the real
APIs (run with ``pytest -m live``)."""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.schemas import WeatherDay, WeatherResult  # noqa: E402


def pytest_configure(config):
    config.addinivalue_line("markers", "live: hits real external APIs")


def fake_weather(city, start, end, today=None):
    days = []
    current = start
    while current <= end:
        rainy = current.day % 3 == 0
        days.append(WeatherDay(
            date=current, condition="Moderate rain" if rainy else "Clear sky",
            icon="rain" if rainy else "sun", weather_code=63 if rainy else 0,
            temp_max_c=31.0, temp_min_c=23.0,
            precipitation_probability=80 if rainy else 5,
            precipitation_mm=12.0 if rainy else 0.0, source="forecast",
            source_note="stub"))
        current += timedelta(days=1)
    return WeatherResult(city=city, resolved_location=f"{city} (stub)",
                         latitude=15.5, longitude=73.8,
                         timezone="Asia/Kolkata", days=days)


@pytest.fixture(autouse=True)
def stub_network(request, monkeypatch):
    if request.node.get_closest_marker("live"):
        return
    monkeypatch.setattr("app.tools.weather_lookup.get_trip_weather",
                        fake_weather)
    monkeypatch.setattr(
        "app.agents.plan_assembler.get_destination_profile",
        lambda city: {"image_url": None, "image_credit": None})
    monkeypatch.setattr(
        "app.api.routes.get_destination_profile",
        lambda city: {"image_url": None, "image_credit": None,
                      "description": None})


@pytest.fixture
def trip_dates():
    start = date.today() + timedelta(days=5)
    return start, start + timedelta(days=3)
