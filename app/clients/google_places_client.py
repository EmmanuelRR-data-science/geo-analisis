"""Google Places API client for nearby business search."""

from __future__ import annotations

import logging
import os
import uuid

import httpx

from app.models.schemas import Business, GoogleReview

logger = logging.getLogger(__name__)

# Timeout and retry configuration
_TIMEOUT = 15.0
_MAX_RETRIES = 1

# Google Places API (New) base URL
_TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
_PLACE_DETAILS_URL = "https://places.googleapis.com/v1/places"


class GooglePlacesClient:
    """Client for Google Places API (New)."""

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or os.getenv("GOOGLE_PLACES_API_KEY", "")

    async def search_nearby(
        self,
        lat: float,
        lng: float,
        radius: int,
        keyword: str,
        max_results: int = 40,
    ) -> list[Business]:
        """Search for businesses near a location using Text Search with pagination.

        Fetches up to *max_results* by following pagination tokens.
        Returns an empty list on any failure (timeout, HTTP error, missing key).
        """
        if not self._api_key:
            logger.warning("GOOGLE_PLACES_API_KEY not configured — skipping Google Places search")
            return []

        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self._api_key,
            "X-Goog-FieldMask": (
                "places.id,places.displayName,places.location,"
                "places.primaryTypeDisplayName,places.rating,"
                "places.userRatingCount,places.currentOpeningHours,"
                "places.photos,places.regularOpeningHours,"
                "places.priceLevel,places.types,places.reviews,"
                "places.editorialSummary,"
                "nextPageToken"
            ),
        }

        all_businesses: list[Business] = []
        page_token: str | None = None
        pages_fetched = 0
        max_pages = max(1, (max_results + 19) // 20)  # ceil(max_results / 20)

        while pages_fetched < max_pages:
            body: dict = {
                "textQuery": keyword,
                "locationBias": {
                    "circle": {
                        "center": {"latitude": lat, "longitude": lng},
                        "radius": float(radius),
                    }
                },
                "maxResultCount": 20,
                "languageCode": "es",
            }
            if page_token:
                body["pageToken"] = page_token

            data = await self._fetch_page(headers, body)
            if data is None:
                break

            page_businesses = self._parse_nearby_results(data)
            all_businesses.extend(page_businesses)
            pages_fetched += 1

            # Check for next page
            page_token = data.get("nextPageToken")
            if not page_token or len(all_businesses) >= max_results:
                break

        return all_businesses[:max_results]

    async def _fetch_page(self, headers: dict, body: dict) -> dict | None:
        """Fetch a single page from the Text Search API with retries."""
        for attempt in range(_MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                    resp = await client.post(
                        _TEXT_SEARCH_URL, json=body, headers=headers
                    )
                    resp.raise_for_status()
                    return resp.json()
            except Exception:
                if attempt < _MAX_RETRIES:
                    logger.warning(
                        "Google Places search attempt %d failed, retrying…",
                        attempt + 1,
                    )
                    continue
                logger.exception("Google Places search failed after retries")
                return None
        return None

    async def get_place_details(self, place_id: str) -> dict | None:
        """Fetch details for a single place. Returns None on failure."""
        if not self._api_key:
            return None

        headers = {
            "X-Goog-Api-Key": self._api_key,
            "X-Goog-FieldMask": (
                "id,displayName,location,primaryTypeDisplayName,"
                "rating,userRatingCount,currentOpeningHours,"
                "regularOpeningHours,photos"
            ),
        }
        url = f"{_PLACE_DETAILS_URL}/{place_id}"

        for attempt in range(_MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                    resp = await client.get(url, headers=headers)
                    resp.raise_for_status()
                    return resp.json()
            except Exception:
                if attempt < _MAX_RETRIES:
                    continue
                logger.exception("Google Places details failed for %s", place_id)
                return None

        return None  # pragma: no cover

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def search_by_category(
        self,
        lat: float,
        lng: float,
        radius: int,
        included_type: str,
        max_results: int = 20,
    ) -> list[Business]:
        """Search for businesses by Google Places category using includedTypes.

        Args:
            lat: Latitude of the search center.
            lng: Longitude of the search center.
            radius: Search radius in metres.
            included_type: Google Places type (e.g. "restaurant", "cafe").
            max_results: Maximum number of results to return.

        Returns:
            List of Business models matching the category.
        """
        if not self._api_key:
            logger.warning("GOOGLE_PLACES_API_KEY not configured — skipping category search")
            return []

        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self._api_key,
            "X-Goog-FieldMask": (
                "places.id,places.displayName,places.location,"
                "places.primaryTypeDisplayName,places.rating,"
                "places.userRatingCount,places.currentOpeningHours,"
                "places.photos,places.regularOpeningHours,"
                "places.priceLevel,places.types,places.reviews,"
                "places.editorialSummary,"
                "nextPageToken"
            ),
        }

        all_businesses: list[Business] = []
        page_token: str | None = None
        pages_fetched = 0
        max_pages = max(1, (max_results + 19) // 20)

        while pages_fetched < max_pages:
            body: dict = {
                "textQuery": included_type,
                "includedType": included_type,
                "locationBias": {
                    "circle": {
                        "center": {"latitude": lat, "longitude": lng},
                        "radius": float(radius),
                    }
                },
                "maxResultCount": 20,
                "languageCode": "es",
            }
            if page_token:
                body["pageToken"] = page_token

            data = await self._fetch_page(headers, body)
            if data is None:
                break

            page_businesses = self._parse_nearby_results(data)
            all_businesses.extend(page_businesses)
            pages_fetched += 1

            page_token = data.get("nextPageToken")
            if not page_token or len(all_businesses) >= max_results:
                break

        return all_businesses[:max_results]

    @staticmethod
    def _parse_nearby_results(data: dict) -> list[Business]:
        """Convert raw API response into Business models."""
        businesses: list[Business] = []
        for place in data.get("places", []):
            location = place.get("location", {})
            display_name = place.get("displayName", {})
            primary_type = place.get("primaryTypeDisplayName", {})

            # Extract opening hours as list of strings
            hours: list[str] | None = None
            reg_hours = place.get("regularOpeningHours", {})
            if reg_hours and "weekdayDescriptions" in reg_hours:
                hours = reg_hours["weekdayDescriptions"]

            # Extract photo references
            photos: list[str] | None = None
            raw_photos = place.get("photos", [])
            if raw_photos:
                photos = [p.get("name", "") for p in raw_photos[:5]]

            # Current opening status
            current_hours = place.get("currentOpeningHours", {})
            is_open: bool | None = current_hours.get("openNow") if current_hours else None

            # Extract priceLevel (0-4)
            price_level: int | None = None
            raw_price = place.get("priceLevel")
            if raw_price is not None:
                # Google may return string like "PRICE_LEVEL_MODERATE" or int
                if isinstance(raw_price, int):
                    price_level = raw_price
                elif isinstance(raw_price, str):
                    _price_map = {
                        "PRICE_LEVEL_FREE": 0,
                        "PRICE_LEVEL_INEXPENSIVE": 1,
                        "PRICE_LEVEL_MODERATE": 2,
                        "PRICE_LEVEL_EXPENSIVE": 3,
                        "PRICE_LEVEL_VERY_EXPENSIVE": 4,
                    }
                    price_level = _price_map.get(raw_price)

            # Extract types
            google_types: list[str] | None = None
            raw_types = place.get("types")
            if raw_types and isinstance(raw_types, list):
                google_types = [str(t) for t in raw_types]

            # Extract reviews (max 5)
            google_reviews: list[GoogleReview] | None = None
            raw_reviews = place.get("reviews")
            if raw_reviews and isinstance(raw_reviews, list):
                parsed_reviews = []
                for rev in raw_reviews[:5]:
                    rev_text_obj = rev.get("text", {})
                    rev_text = rev_text_obj.get("text", "") if isinstance(rev_text_obj, dict) else str(rev_text_obj)
                    rev_rating = rev.get("rating", 0)
                    if rev_text:
                        parsed_reviews.append(GoogleReview(text=rev_text, rating=int(rev_rating)))
                google_reviews = parsed_reviews if parsed_reviews else None

            # Extract editorialSummary
            editorial_summary: str | None = None
            raw_summary = place.get("editorialSummary")
            if raw_summary:
                if isinstance(raw_summary, dict):
                    editorial_summary = raw_summary.get("text")
                elif isinstance(raw_summary, str):
                    editorial_summary = raw_summary

            businesses.append(
                Business(
                    id=place.get("id", str(uuid.uuid4())),
                    name=display_name.get("text", "Sin nombre"),
                    lat=location.get("latitude", 0.0),
                    lng=location.get("longitude", 0.0),
                    category=primary_type.get("text", ""),
                    source="google",
                    verified_google=True,
                    google_rating=place.get("rating"),
                    google_reviews_count=place.get("userRatingCount"),
                    google_hours=hours,
                    google_photos=photos,
                    google_is_open=is_open,
                    google_price_level=price_level,
                    google_types=google_types,
                    google_reviews=google_reviews,
                    google_editorial_summary=editorial_summary,
                )
            )
        return businesses
