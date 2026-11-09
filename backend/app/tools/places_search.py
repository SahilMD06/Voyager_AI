"""Tool 3 - Places / attractions discovery over places.json."""

from __future__ import annotations

from app.models.schemas import Interest, PlaceOption, PlacesSearchResult
from app.services.data_repository import (
    DatasetRepository, get_repository, normalise_city,
)

# Which place categories satisfy which interests.
INTEREST_CATEGORIES: dict[Interest, set[str]] = {
    Interest.ADVENTURE: {"fort", "park", "lake", "beach"},
    Interest.BEACHES: {"beach", "lake"},
    Interest.HISTORICAL: {"fort", "monument", "museum", "temple"},
    Interest.NATURE: {"park", "lake", "beach"},
    Interest.FOOD: {"market"},
    Interest.SHOPPING: {"market"},
    Interest.CULTURE: {"museum", "temple", "monument", "market"},
    Interest.SPIRITUAL: {"temple"},
}

# Per-person entry/activity cost ESTIMATES by category (INR). These are not
# in the dataset and are always labelled as estimates.
CATEGORY_COST_ESTIMATE: dict[str, int] = {
    "museum": 200, "fort": 300, "monument": 250, "temple": 0,
    "park": 50, "lake": 150, "beach": 0, "market": 0,
}


def discover_places(
    city: str,
    interests: list[Interest] | None = None,
    min_rating: float = 0.0,
    max_results: int = 10,
    repo: DatasetRepository | None = None,
) -> PlacesSearchResult:
    """Rank attractions in ``city`` by rating and interest match.

    Duplicate names in the same city are collapsed (keeping the best rated)
    so the itinerary does not repeat a place.
    """
    repo = repo or get_repository()
    city = normalise_city(city, repo)
    interests = interests or []
    frame = repo.places[repo.places["city"].str.lower() == city.lower()]
    if frame.empty:
        return PlacesSearchResult(
            city=city, interests=[i.value for i in interests], options=[],
            note=f"places.json has no attractions in {city}.",
        )

    frame = frame[frame["rating"] >= min_rating]
    frame = frame.sort_values("rating", ascending=False).drop_duplicates(
        subset=["name"], keep="first"
    )

    options: list[PlaceOption] = []
    for _, row in frame.iterrows():
        category = row["type"]
        matched = [i.value for i in interests
                   if category in INTEREST_CATEGORIES.get(i, set())]
        interest_score = (len(matched) / len(interests)) if interests else 0.5
        score = 0.6 * (row["rating"] / 5) + 0.4 * interest_score
        reason = f"Rated {row['rating']}/5 {category}"
        if matched:
            reason += f"; fits your interest in {', '.join(matched)}"
        elif interests:
            reason += "; not a direct interest match but highly rated locally"
        options.append(PlaceOption(
            place_id=row["place_id"], name=row["name"], city=row["city"],
            category=category, rating=float(row["rating"]),
            matched_interests=matched,
            estimated_entry_cost=CATEGORY_COST_ESTIMATE.get(category, 100),
            score=round(float(score), 4), reason=reason + ".",
        ))

    options.sort(key=lambda o: o.score, reverse=True)
    note = f"{len(options)} unique attraction(s) in {city} in places.json."
    if interests and not any(o.matched_interests for o in options):
        note += " None match the selected interests directly."
    return PlacesSearchResult(
        city=city, interests=[i.value for i in interests],
        options=options[:max_results], note=note,
    )
