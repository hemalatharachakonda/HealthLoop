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
from math import radians, sin, cos, sqrt, atan2
from curated_hospitals import VIJAYAWADA_HOSPITALS, is_in_vijayawada

OVERPASS_URL = "https://overpass-api.de/api/interpreter"


def _distance_km(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 6371 * 2 * atan2(sqrt(a), sqrt(1 - a))


def _match_curated_hospitals(lat: float, lon: float, specialty: str | None, is_emergency: bool, radius_m: int):
    """
    Vijayawada-specific: match against real, specialty-tagged hospitals instead of the
    generic Overpass data (which has no specialty info at all). See curated_hospitals.py
    for why this exists and its limits.
    """
    if not is_in_vijayawada(lat, lon):
        return []

    specialty_lower = (specialty or "").strip().lower()
    results = []
    for h in VIJAYAWADA_HOSPITALS:
        dist_km = _distance_km(lat, lon, h["lat"], h["lon"])
        if dist_km * 1000 > radius_m:
            continue
        if is_emergency and not h["is_24_7_emergency"]:
            continue

        specialty_match = False
        if specialty_lower:
            specialty_match = any(specialty_lower in s.lower() or s.lower() in specialty_lower
                                   for s in h["specialties"])

        if is_emergency:
            status = "24/7 Emergency"
        elif specialty_match:
            status = f"Confirmed {specialty}" if specialty else "Open now"
        else:
            status = "Open now"  # all curated entries are 24/7-listed on Google, per the source data

        results.append({
            "name": h["name"],
            "lat": h["lat"],
            "lon": h["lon"],
            "phone": h["phone"],
            "address": h["address"],
            "specialties": h["specialties"],
            "specialty_match": specialty_match,
            "status": status,
            "distance_km": round(dist_km, 1),
            "source": "curated",
        })

    # Specialty-confirmed matches first, then by distance
    results.sort(key=lambda r: (0 if r["specialty_match"] else 1, r["distance_km"]))
    return results


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


def find_hospitals(lat: float, lon: float, is_emergency: bool, radius_m: int = 5000,
                    limit: int = 8, specialty: str | None = None):
    """
    Main entry point.
    is_emergency=True  -> only return hospitals with confirmed or likely 24/7 emergency capability
    is_emergency=False -> return hospitals/clinics, prioritizing ones confirmed open right now
    specialty          -> if the location is in/near Vijayawada, prioritizes hospitals from the
                           curated list (curated_hospitals.py) confirmed to offer that specialty,
                           since free location APIs don't have real specialty data. Outside
                           Vijayawada, this has no effect - falls back to Overpass-only results,
                           which can't be specialty-filtered.
    """
    curated_results = _match_curated_hospitals(lat, lon, specialty, is_emergency, radius_m)

    # OSM/Overpass is a free, best-effort supplement to the curated list - if it fails
    # (network issue, Overpass rate limit, timeout), that should never wipe out curated
    # results that already succeeded. Fail soft here, not hard.
    try:
        raw_places = _fetch_raw_places(lat, lon, radius_m)
    except Exception:
        raw_places = []

    osm_results = []
    curated_names = {h["name"].lower() for h in curated_results}

    for p in raw_places:
        if (p["name"] or "").lower() in curated_names:
            continue  # avoid duplicate listing of a hospital that's already in curated_results

        is_24_7 = _is_24_7(p["opening_hours_raw"], p["amenity_type"], p["has_emergency_tag"])
        open_now = _currently_open(p["opening_hours_raw"])

        if is_emergency:
            # Emergency mode: only surface hospitals (not small clinics) that are confirmed 24/7,
            # OR unconfirmed full hospitals (better to show with a caveat than hide a real option
            # during an emergency) - clinics without emergency tags are excluded entirely.
            if p["amenity_type"] == "hospital" and (is_24_7 or p["opening_hours_raw"] is None):
                osm_results.append({**p, "status": "24/7 Emergency" if is_24_7 else "Emergency care likely available - call to confirm", "source": "osm"})
            elif is_24_7:
                osm_results.append({**p, "status": "24/7 Emergency", "source": "osm"})
        else:
            # Routine mode: prefer places we can confirm are open now; still include "unknown" ones
            # lower in the list rather than dropping them, since OSM hours data is often incomplete.
            if open_now is True:
                osm_results.append({**p, "status": "Open now", "source": "osm"})
            elif open_now is None:
                osm_results.append({**p, "status": "Hours unclear - call ahead", "source": "osm"})
            # open_now is False -> deliberately excluded from routine mode results

    # Sort OSM results: confirmed-open / confirmed-24/7 first, then unconfirmed
    def sort_key(r):
        return 0 if r["status"] in ("24/7 Emergency", "Open now") else 1

    osm_results.sort(key=sort_key)

    # Curated (specialty-verified) results always lead, since they're the more trustworthy data.
    combined = curated_results + osm_results
    return combined[:limit]
