"""
Curated hospital + specialty data for Vijayawada, Andhra Pradesh.

WHY THIS FILE EXISTS:
Free location APIs (OpenStreetMap Overpass, and even Google Places' free tier) don't
reliably tag which medical specialties a hospital actually offers - that's paid/manually
curated data at scale. So when Groq recommends a specialty (e.g. "Cardiology"), the
generic Overpass-based lookup in hospital_finder.py can only filter by open/emergency
status, not by whether a hospital actually has a cardiology department.

This file closes that gap FOR VIJAYAWADA SPECIFICALLY with real, manually verified data
(hospital names, addresses, coordinates, and specialty lists were checked against each
hospital's own site/listings, not invented) so the demo can make an honest, accurate claim:
"we matched you to a hospital that actually has this specialty," not just "a nearby hospital."

This is intentionally NOT a general solution - it only covers Vijayawada. Outside this
city, hospital_finder.py falls back to the Overpass-based open/emergency-only filtering.
Extending to more cities means adding more curated entries here (or eventually paying for
a data source with real specialty tagging, e.g. Google Places' paid Business Profile data).

Coordinates/phone numbers pulled from Google Places listings, cross-checked against each
hospital's own site for specialty lists. Verify before using in a real (non-demo) context -
hospitals add/drop departments and this list will go stale over time.
"""

VIJAYAWADA_CENTER = (16.5062, 80.6480)  # rough city center, used only to decide if a
                                          # search location is "in Vijayawada" for this list

VIJAYAWADA_HOSPITALS = [
    {
        "name": "Aster Ramesh Hospital",
        "address": "MG Rd, opposite Indira Gandhi Municipal Stadium, Labbipet, Vijayawada, AP 520010",
        "lat": 16.5028427,
        "lon": 80.6388938,
        "phone": "+91 866 247 2000",
        "specialties": [
            "Cardiology", "Neurology", "Neurosurgery", "Orthopedics", "Gastroenterology",
            "Urology", "Diabetology", "Pulmonology", "Psychiatry", "Emergency Medicine", "Trauma",
        ],
        "is_24_7_emergency": True,
    },
    {
        "name": "Manipal Hospital Vijayawada",
        "address": "12-570, near Kanakadurga Varadhi, Tadepalle, Vijayawada, AP 522501",
        "lat": 16.4844754,
        "lon": 80.6169548,
        "phone": "+91 1800 102 4647",
        "specialties": [
            "General Medicine", "Urology", "General Surgery", "Orthopedics", "Pediatrics",
            "Gynecology", "ENT", "Emergency Medicine",
        ],
        "is_24_7_emergency": True,
    },
    {
        "name": "Union Hospitals",
        "address": "29-4-7, Kodandarami Reddy St, Governorpet, Vijayawada, AP 520002",
        "lat": 16.5127184,
        "lon": 80.6310223,
        "phone": "+91 83949 59108",
        "specialties": [
            "Orthopedics", "Neurosurgery", "Gastroenterology", "General Surgery",
            "General Medicine", "Nephrology", "ENT", "Plastic Surgery", "Critical Care",
        ],
        "is_24_7_emergency": True,
    },
    {
        "name": "Amaravati Multispeciality Hospital",
        "address": "Beside Maruti True Value, Enikepadu, Vijayawada, AP 521108",
        "lat": 16.5132868,
        "lon": 80.7083723,
        "phone": "+91 90444 91999",
        "specialties": [
            "Neurosurgery", "Cardiology", "Spine Surgery", "Neurology", "Psychiatry",
            "Urology", "Orthopedics", "ENT", "Diabetology", "General Medicine",
            "Gynecology", "Critical Care", "Gastroenterology", "Emergency Medicine",
        ],
        "is_24_7_emergency": True,
    },
    {
        "name": "Nagarjuna Hospital",
        "address": "8-102, Chalasani Nagar, Kanuru, Vijayawada, AP 520007",
        "lat": 16.487498,
        "lon": 80.6842563,
        "phone": "+91 99634 14242",
        "specialties": [
            "General Surgery", "Gastroenterology", "Orthopedics", "Neurology",
            "Physiotherapy & Rehabilitation", "Emergency Medicine",
        ],
        "is_24_7_emergency": True,
    },
    {
        "name": "NRI General Hospital",
        "address": "NRI Hospital Road, Chinnakakani, Mangalagiri, AP 522508",
        "lat": 16.4140663,
        "lon": 80.5576969,
        "phone": "+91 86452 37404",
        "specialties": [
            "General Medicine", "Neurology", "Nephrology", "Psychiatry", "Vascular Surgery",
            "Orthopedics", "Pediatrics", "Emergency Medicine",
        ],
        "is_24_7_emergency": True,
    },
    {
        "name": "Government General Hospital (New GGH, Gunadala)",
        "address": "NH 16 Service Rd, beside NTR Health University, Gunadala, Kanuru, AP 520008",
        "lat": 16.5164879,
        "lon": 80.6702523,
        "phone": None,
        "specialties": [
            "General Medicine", "Cardiology", "Emergency Medicine", "Trauma",
        ],
        "is_24_7_emergency": True,
    },
    {
        "name": "Government General Hospital (Old GGH, Hanumanpet)",
        "address": "Old Bus Stand Road, Hanumanpet, Vijayawada, AP 520003",
        "lat": 16.5133387,
        "lon": 80.6189892,
        "phone": None,
        "specialties": [
            "Obstetrics & Gynecology", "Neonatal Care",
        ],
        "is_24_7_emergency": True,
    },
    {
        "name": "INDLAS Hospitals",
        "address": "Devi Oil Mill Rd, Vishnu Vardhana Rao St, Suryaraopeta, Governorpet, Vijayawada, AP 520002",
        "lat": 16.5136625,
        "lon": 80.6346418,
        "phone": "+91 866 243 2040",
        "specialties": [
            "Psychiatry", "Mental Health", "De-addiction",
        ],
        "is_24_7_emergency": False,  # specialty mental-health/rehab center, not a trauma/ER hospital
    },
    {
        "name": "Sunrise Hospitals",
        "address": "33-13-5, Bellapu Sobhanadri St, Moghalrajapuram, Suryaraopeta, Vijayawada, AP 520002",
        "lat": 16.5128381,
        "lon": 80.6391539,
        "phone": "+91 866 243 4646",
        "specialties": [
            "Orthopedics", "Pediatrics",
        ],
        "is_24_7_emergency": True,
    },
    {
        "name": "Shreyas Ortho & Skin Multispeciality Hospital",
        "address": "76-17-4, beside Urmila Nagar Church, Bhavanipuram, Vijayawada, AP 520012",
        "lat": 16.5384146,
        "lon": 80.5996132,
        "phone": "+91 91549 65555",
        "specialties": [
            "Orthopedics", "Dermatology", "General Medicine", "Diabetology",
            "Endocrinology", "Cardiology", "Pulmonology", "Gynecology", "Pediatrics",
        ],
        "is_24_7_emergency": True,
    },
]


def is_in_vijayawada(lat: float, lon: float, tolerance_km: float = 25) -> bool:
    """Rough check: is this search location close enough to Vijayawada for the curated
    list to be relevant? Anything further out falls back to the generic Overpass lookup."""
    from math import radians, sin, cos, sqrt, atan2
    lat1, lon1 = radians(lat), radians(lon)
    lat2, lon2 = radians(VIJAYAWADA_CENTER[0]), radians(VIJAYAWADA_CENTER[1])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    distance_km = 6371 * 2 * atan2(sqrt(a), sqrt(1 - a))
    return distance_km <= tolerance_km
