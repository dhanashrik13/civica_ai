# --- CIVIC GOVERNANCE CONSTANTS ---

GOVERNMENT_DEPARTMENTS = [
    ("pwd", "Public Works Department (PWD)"),
    ("water_supply", "Water Supply Department"),
    ("sanitation", "Sanitation Department"),
    ("electricity", "Electricity Department"),
    ("road_transport", "Road & Transport Department"),
    ("drainage_sewerage", "Drainage & Sewerage Department"),
    ("health", "Health Department"),
    ("environment", "Environment Department"),
    ("urban_planning", "Urban Planning Department"),
    ("disaster_management", "Disaster Management Department"),
    ("traffic_police", "Traffic Police Department"),
    ("municipal_engineering", "Municipal Engineering Department"),
]

LEGACY_CATEGORY_MAPPING = {
    "pothole": "pwd",
    "road_damage": "pwd",
    "water_leakage": "water_supply",
    "street_light": "electricity",
    "garbage": "sanitation",
    "drainage": "drainage_sewerage",
}
