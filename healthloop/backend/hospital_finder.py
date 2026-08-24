"""
Nearby hospital lookup with emergency-vs-routine filtering.

Uses the OpenStreetMap Overpass API - completely free, no API key, no billing account needed.
(Swap in Google Places Nearby Search later if you want richer data - same filtering logic applies,
 just change how `raw_places` is populated in find_hospitals().)

Key idea: a hospital that's "closed" for routine OPD consultation may still run a 24/7 emergency
department. So emergency situations and routine situations need different filters, not just
"open now" for everything.
"""
import requests
from datetime import datetime

OVERPASS_URL = "https://overpass-api.de/api/interpreter"


def _build_query(lat: float, lon: float, radius_m: int = 5000) -> str:
    # Pulls hospitals AND clinics/doctors within radius, with whatever tags OSM has for each.
    return f"""
    [out:json][timeout:25];
    (
      node["amenity"="hospital"](around:{radius_m},{lat},{lon});
      way["amenity"="hospital"](around:{radius_m},{lat},{lon});
      node["amenity"="clinic"](around:{radius_m},{lat},{lon});
      way["amenity"="clinic"](around:{radius_m},{lat},{lon});
    );
    out center tags;
    """


def _fetch_raw_places(lat: float, lon: float, radius_m: int = 5000) -> list:
    query = _build_query(lat, lon, radius_m)
    resp = requests.post(OVERPASS_URL, data={"data": query}, timeout=30)
    resp.raise_for_status()
    elements = resp.json().get("elements", [])

    places = []
    for el in elements:
        tags = el.get("tags", {})
        name = tags.get("name")
        if not name:
            continue  # skip unnamed nodes, not useful to show a user

        lat_ = el.get("lat") or el.get("center", {}).get("lat")
        lon_ = el.get("lon") or el.get("center", {}).get("lon")

        places.append({
            "name": name,
            "lat": lat_,
            "lon": lon_,
            "phone": tags.get("phone") or tags.get("contact:phone"),
            "opening_hours_raw": tags.get("opening_hours"),  # OSM's raw string, e.g. "24/7" or "Mo-Fr 09:00-18:00"
            "has_emergency_tag": tags.get("emergency") == "yes",
            "amenity_type": tags.get("amenity"),
            # OSM doesn't have Google-style ratings; that's a known trade-off of the free option.
        })
    return places


def _is_24_7(opening_hours_raw: str | None, amenity_type: str, has_emergency_tag: bool) -> bool:
    """
    Best-effort check for round-the-clock emergency capability.
    OSM data completeness varies, so we're deliberately generous here:
    - explicit "24/7" tag -> yes
    - tagged with emergency=yes -> treat as having emergency capability regardless of OPD hours
    - a full "hospital" (not a small "clinic") with no listed hours -> assume it likely has some
      emergency capability, since most standalone hospitals do; flag it as "unconfirmed" for the UI
      to show a caveat rather than hiding it outright
    """
    if opening_hours_raw and "24/7" in opening_hours_raw:
        return True
    if has_emergency_tag:
        return True
    return False


def _currently_open(opening_hours_raw: str | None) -> bool | None:
    """
    Very simple open-now check for routine (non-emergency) mode.
    Returns True/False if we can determine it, or None if data is missing/unparseable
    (OSM's opening_hours syntax is rich - for a hackathon, a light heuristic is enough;
    for production, use a proper opening_hours parser library).
    """
    if not opening_hours_raw:
        return None
    if "24/7" in opening_hours_raw:
        return True
    # Minimal heuristic: not attempting full day/time parsing here for hackathon scope.
    # Returning None (unknown) rather than guessing wrong is safer than a false "open".
    return None


def find_hospitals(lat: float, lon: float, is_emergency: bool, radius_m: int = 5000, limit: int = 8):
    """
    Main entry point.
    is_emergency=True  -> only return hospitals with confirmed or likely 24/7 emergency capability
    is_emergency=False -> return hospitals/clinics, prioritizing ones confirmed open right now
    """
    raw_places = _fetch_raw_places(lat, lon, radius_m)
    results = []

    for p in raw_places:
        is_24_7 = _is_24_7(p["opening_hours_raw"], p["amenity_type"], p["has_emergency_tag"])
        open_now = _currently_open(p["opening_hours_raw"])

        if is_emergency:
            # Emergency mode: only surface hospitals (not small clinics) that are confirmed 24/7,
            # OR unconfirmed full hospitals (better to show with a caveat than hide a real option
            # during an emergency) - clinics without emergency tags are excluded entirely.
            if p["amenity_type"] == "hospital" and (is_24_7 or p["opening_hours_raw"] is None):
                results.append({**p, "status": "24/7 Emergency" if is_24_7 else "Emergency care likely available - call to confirm"})
            elif is_24_7:
                results.append({**p, "status": "24/7 Emergency"})
        else:
            # Routine mode: prefer places we can confirm are open now; still include "unknown" ones
            # lower in the list rather than dropping them, since OSM hours data is often incomplete.
            if open_now is True:
                results.append({**p, "status": "Open now"})
            elif open_now is None:
                results.append({**p, "status": "Hours unclear - call ahead"})
            # open_now is False -> deliberately excluded from routine mode results

    # Sort: confirmed-open / confirmed-24/7 first, then unconfirmed
    def sort_key(r):
        return 0 if r["status"] in ("24/7 Emergency", "Open now") else 1

    results.sort(key=sort_key)
    return results[:limit]
