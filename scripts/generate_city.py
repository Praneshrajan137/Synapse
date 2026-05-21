"""
scripts/generate_city.py

Generate synthetic dark store network, demand data, rider fleet, supplier
relationships, and zone definitions for a given city.

Supports:  bengaluru | mumbai
Both cities produce structurally identical outputs so that transfer learning
across cities works with zero schema changes.

Usage:
    python scripts/generate_city.py --city mumbai --stores 25 --days 90 --seed 42
    python scripts/generate_city.py --city bengaluru --stores 25 --days 90 --seed 42

INVARIANT I-8: Deterministic via --seed for reproducible ML pipelines.
"""

from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import structlog

log = structlog.get_logger()

# ─── SHARED SKU CATALOG (city-agnostic, identical across cities) ─────────────

CATEGORIES = [
    ("Essentials", ["Rice", "Wheat", "Oil", "Sugar", "Salt", "Pulses", "Tea", "Coffee"]),
    ("Snacks & Beverages", ["Chips", "Biscuits", "Namkeen", "Juice", "Soda", "Water"]),
    ("Fresh Produce", ["Tomato", "Onion", "Potato", "Banana", "Apple", "Spinach"]),
    ("Dairy & Bakery", ["Milk", "Curd", "Bread", "Butter", "Paneer", "Cheese"]),
    ("Household", ["Soap", "Detergent", "Cleaner", "Tissue", "Foil", "Garbage Bags"]),
    ("Personal Care", ["Shampoo", "Toothpaste", "Deo", "Facewash", "Cream", "Razor"]),
    ("Sweets & Dry Fruits", ["Ladoo", "Barfi", "Almonds", "Cashews", "Raisins", "Dates"]),
    ("Fasting Foods", ["Sabudana", "Kuttu Flour", "Rajgira", "Peanuts", "Rock Salt"]),
    ("Gifting", ["Gift Box", "Chocolate Pack", "Hamper", "Candle Set", "Diya Set"]),
]


def _generate_sku_catalog(rng: np.random.Generator, n_skus: int) -> list[dict[str, Any]]:
    skus: list[dict[str, Any]] = []
    idx = 0
    while idx < n_skus:
        for cat_name, subcats in CATEGORIES:
            for subcat in subcats:
                if idx >= n_skus:
                    break
                sku_id = f"SKU-{idx + 1:04d}"
                variant = idx // len(subcats) + 1
                is_essential = cat_name in ("Essentials", "Fresh Produce", "Dairy & Bakery")
                is_perishable = cat_name in ("Fresh Produce", "Dairy & Bakery")
                skus.append({
                    "sku_id": sku_id,
                    "name": f"{subcat} Variant {variant}",
                    "category": cat_name,
                    "subcategory": subcat,
                    "is_essential": is_essential,
                    "is_perishable": is_perishable,
                    "shelf_life_days": int(rng.choice([3, 7, 14, 30, 90, 365],
                        p=[0.1, 0.15, 0.15, 0.2, 0.2, 0.2])),
                    "base_price_inr": round(float(rng.uniform(10, 500)), 2),
                    "weight_kg": round(float(rng.uniform(0.1, 5.0)), 2),
                })
                idx += 1
    return skus


# ─── CITY PROFILES ───────────────────────────────────────────────────────────

BENGALURU_STORES = [
    {"id": "BLR-001", "name": "Koramangala 1", "lat": 12.9352, "lon": 77.6245, "zone": "koramangala"},
    {"id": "BLR-002", "name": "Koramangala 2", "lat": 12.9280, "lon": 77.6190, "zone": "koramangala"},
    {"id": "BLR-003", "name": "Indiranagar 1", "lat": 12.9716, "lon": 77.6412, "zone": "indiranagar"},
    {"id": "BLR-004", "name": "Indiranagar 2", "lat": 12.9780, "lon": 77.6380, "zone": "indiranagar"},
    {"id": "BLR-005", "name": "HSR Layout 1", "lat": 12.9116, "lon": 77.6474, "zone": "hsr"},
    {"id": "BLR-006", "name": "HSR Layout 2", "lat": 12.9150, "lon": 77.6520, "zone": "hsr"},
    {"id": "BLR-007", "name": "Whitefield 1", "lat": 12.9698, "lon": 77.7500, "zone": "whitefield"},
    {"id": "BLR-008", "name": "Whitefield 2", "lat": 12.9750, "lon": 77.7450, "zone": "whitefield"},
    {"id": "BLR-009", "name": "Electronic City 1", "lat": 12.8452, "lon": 77.6602, "zone": "electronic_city"},
    {"id": "BLR-010", "name": "Electronic City 2", "lat": 12.8500, "lon": 77.6550, "zone": "electronic_city"},
    {"id": "BLR-011", "name": "Jayanagar", "lat": 12.9308, "lon": 77.5838, "zone": "jayanagar"},
    {"id": "BLR-012", "name": "JP Nagar", "lat": 12.9063, "lon": 77.5857, "zone": "jayanagar"},
    {"id": "BLR-013", "name": "Marathahalli 1", "lat": 12.9591, "lon": 77.7009, "zone": "marathahalli"},
    {"id": "BLR-014", "name": "Marathahalli 2", "lat": 12.9560, "lon": 77.6950, "zone": "marathahalli"},
    {"id": "BLR-015", "name": "Bellandur", "lat": 12.9256, "lon": 77.6762, "zone": "bellandur"},
    {"id": "BLR-016", "name": "Sarjapur Road", "lat": 12.9100, "lon": 77.6850, "zone": "bellandur"},
    {"id": "BLR-017", "name": "Bannerghatta Road", "lat": 12.8880, "lon": 77.5970, "zone": "bannerghatta"},
    {"id": "BLR-018", "name": "BTM Layout", "lat": 12.9166, "lon": 77.6101, "zone": "btm"},
    {"id": "BLR-019", "name": "Hebbal", "lat": 13.0358, "lon": 77.5970, "zone": "hebbal"},
    {"id": "BLR-020", "name": "Yelahanka", "lat": 13.1005, "lon": 77.5940, "zone": "yelahanka"},
    {"id": "BLR-021", "name": "Rajajinagar", "lat": 12.9860, "lon": 77.5530, "zone": "rajajinagar"},
    {"id": "BLR-022", "name": "Malleshwaram", "lat": 13.0035, "lon": 77.5640, "zone": "malleshwaram"},
    {"id": "BLR-023", "name": "Basavanagudi", "lat": 12.9430, "lon": 77.5740, "zone": "basavanagudi"},
    {"id": "BLR-024", "name": "Domlur", "lat": 12.9610, "lon": 77.6387, "zone": "indiranagar"},
    {"id": "BLR-025", "name": "Kormangala 3", "lat": 12.9340, "lon": 77.6300, "zone": "koramangala"},
]

BENGALURU_WAREHOUSES = [
    {"id": "WH-BLR-001", "name": "Nelamangala Logistics Hub", "lat": 13.0990, "lon": 77.3910,
     "type": "central", "capacity_pallets": 5000},
    {"id": "WH-BLR-002", "name": "Hosur Road Warehouse", "lat": 12.8340, "lon": 77.6560,
     "type": "satellite", "capacity_pallets": 2000},
    {"id": "WH-BLR-003", "name": "Whitefield Distribution Center", "lat": 12.9810, "lon": 77.7620,
     "type": "satellite", "capacity_pallets": 1500},
]

BENGALURU_ZONES = [
    {"id": "ZONE-BLR-KOR", "name": "koramangala", "population_density": "very_high",
     "avg_income": "high", "flood_risk": "low"},
    {"id": "ZONE-BLR-IND", "name": "indiranagar", "population_density": "high",
     "avg_income": "high", "flood_risk": "low"},
    {"id": "ZONE-BLR-HSR", "name": "hsr", "population_density": "high",
     "avg_income": "high", "flood_risk": "low"},
    {"id": "ZONE-BLR-WF", "name": "whitefield", "population_density": "high",
     "avg_income": "medium", "flood_risk": "low"},
    {"id": "ZONE-BLR-EC", "name": "electronic_city", "population_density": "medium",
     "avg_income": "medium", "flood_risk": "low"},
    {"id": "ZONE-BLR-JN", "name": "jayanagar", "population_density": "high",
     "avg_income": "high", "flood_risk": "low"},
    {"id": "ZONE-BLR-MR", "name": "marathahalli", "population_density": "very_high",
     "avg_income": "medium", "flood_risk": "low"},
    {"id": "ZONE-BLR-BL", "name": "bellandur", "population_density": "high",
     "avg_income": "high", "flood_risk": "medium"},
    {"id": "ZONE-BLR-BG", "name": "bannerghatta", "population_density": "medium",
     "avg_income": "medium", "flood_risk": "low"},
    {"id": "ZONE-BLR-BTM", "name": "btm", "population_density": "very_high",
     "avg_income": "medium", "flood_risk": "low"},
    {"id": "ZONE-BLR-HB", "name": "hebbal", "population_density": "medium",
     "avg_income": "medium", "flood_risk": "low"},
    {"id": "ZONE-BLR-YK", "name": "yelahanka", "population_density": "medium",
     "avg_income": "medium", "flood_risk": "low"},
    {"id": "ZONE-BLR-RJ", "name": "rajajinagar", "population_density": "high",
     "avg_income": "medium", "flood_risk": "low"},
    {"id": "ZONE-BLR-ML", "name": "malleshwaram", "population_density": "high",
     "avg_income": "high", "flood_risk": "low"},
    {"id": "ZONE-BLR-BV", "name": "basavanagudi", "population_density": "high",
     "avg_income": "high", "flood_risk": "low"},
]

MUMBAI_STORES = [
    {"id": "MUM-001", "name": "Colaba", "lat": 18.9067, "lon": 72.8147, "zone": "south"},
    {"id": "MUM-002", "name": "Lower Parel", "lat": 18.9932, "lon": 72.8302, "zone": "south"},
    {"id": "MUM-003", "name": "Dadar", "lat": 19.0178, "lon": 72.8478, "zone": "central"},
    {"id": "MUM-004", "name": "Bandra West", "lat": 19.0596, "lon": 72.8295, "zone": "western_suburbs"},
    {"id": "MUM-005", "name": "Bandra East", "lat": 19.0590, "lon": 72.8497, "zone": "western_suburbs"},
    {"id": "MUM-006", "name": "Andheri West", "lat": 19.1197, "lon": 72.8464, "zone": "western_suburbs"},
    {"id": "MUM-007", "name": "Andheri East", "lat": 19.1136, "lon": 72.8697, "zone": "western_suburbs"},
    {"id": "MUM-008", "name": "Kurla", "lat": 19.0726, "lon": 72.8793, "zone": "central_suburbs"},
    {"id": "MUM-009", "name": "Ghatkopar", "lat": 19.0860, "lon": 72.9080, "zone": "central_suburbs"},
    {"id": "MUM-010", "name": "Powai", "lat": 19.1176, "lon": 72.9060, "zone": "central_suburbs"},
    {"id": "MUM-011", "name": "Goregaon", "lat": 19.1553, "lon": 72.8490, "zone": "western_suburbs"},
    {"id": "MUM-012", "name": "Malad", "lat": 19.1868, "lon": 72.8484, "zone": "western_suburbs"},
    {"id": "MUM-013", "name": "Kandivali", "lat": 19.2047, "lon": 72.8525, "zone": "western_suburbs"},
    {"id": "MUM-014", "name": "Borivali", "lat": 19.2307, "lon": 72.8567, "zone": "western_suburbs"},
    {"id": "MUM-015", "name": "Dahisar", "lat": 19.2588, "lon": 72.8626, "zone": "western_suburbs"},
    {"id": "MUM-016", "name": "Vikhroli", "lat": 19.1067, "lon": 72.9283, "zone": "central_suburbs"},
    {"id": "MUM-017", "name": "Mulund", "lat": 19.1726, "lon": 72.9563, "zone": "central_suburbs"},
    {"id": "MUM-018", "name": "Thane", "lat": 19.2183, "lon": 72.9781, "zone": "thane"},
    {"id": "MUM-019", "name": "Chembur", "lat": 19.0522, "lon": 72.8994, "zone": "harbour"},
    {"id": "MUM-020", "name": "Vashi", "lat": 19.0771, "lon": 72.9986, "zone": "navi_mumbai"},
    {"id": "MUM-021", "name": "Nerul", "lat": 19.0330, "lon": 73.0169, "zone": "navi_mumbai"},
    {"id": "MUM-022", "name": "Kharghar", "lat": 19.0474, "lon": 73.0680, "zone": "navi_mumbai"},
    {"id": "MUM-023", "name": "Panvel", "lat": 18.9894, "lon": 73.1175, "zone": "navi_mumbai"},
    {"id": "MUM-024", "name": "Airoli", "lat": 19.1551, "lon": 72.9983, "zone": "navi_mumbai"},
    {"id": "MUM-025", "name": "Mira Road", "lat": 19.2812, "lon": 72.8685, "zone": "extended_western"},
]

MUMBAI_WAREHOUSES = [
    {"id": "WH-MUM-001", "name": "Bhiwandi Logistics Hub", "lat": 19.2967, "lon": 73.0631,
     "type": "central", "capacity_pallets": 5000},
    {"id": "WH-MUM-002", "name": "Navi Mumbai Warehouse", "lat": 19.0330, "lon": 73.0297,
     "type": "satellite", "capacity_pallets": 2000},
    {"id": "WH-MUM-003", "name": "Thane Distribution Center", "lat": 19.1860, "lon": 72.9747,
     "type": "satellite", "capacity_pallets": 1500},
]

MUMBAI_ZONES = [
    {"id": "ZONE-MUM-SOUTH", "name": "south",
     "population_density": "medium", "avg_income": "high", "flood_risk": "low"},
    {"id": "ZONE-MUM-CENTRAL", "name": "central",
     "population_density": "very_high", "avg_income": "medium", "flood_risk": "high"},
    {"id": "ZONE-MUM-WESTERN", "name": "western_suburbs",
     "population_density": "very_high", "avg_income": "medium", "flood_risk": "medium"},
    {"id": "ZONE-MUM-CENTRAL-SUB", "name": "central_suburbs",
     "population_density": "high", "avg_income": "medium", "flood_risk": "medium"},
    {"id": "ZONE-MUM-HARBOUR", "name": "harbour",
     "population_density": "high", "avg_income": "low", "flood_risk": "high"},
    {"id": "ZONE-MUM-THANE", "name": "thane",
     "population_density": "medium", "avg_income": "medium", "flood_risk": "low"},
    {"id": "ZONE-MUM-NAVI", "name": "navi_mumbai",
     "population_density": "medium", "avg_income": "medium", "flood_risk": "low"},
    {"id": "ZONE-MUM-EXT-WEST", "name": "extended_western",
     "population_density": "medium", "avg_income": "low", "flood_risk": "medium"},
]

CITY_PROFILES: dict[str, dict[str, Any]] = {
    "bengaluru": {
        "stores": BENGALURU_STORES,
        "warehouses": BENGALURU_WAREHOUSES,
        "zones": BENGALURU_ZONES,
        "base_demand_multiplier": 1.0,
        "peak_hour_amplification": 1.4,
        "avg_delivery_time_min": 14,
        "rider_speed_kmh_peak": 18,
        "rider_speed_kmh_offpeak": 28,
        "avg_lead_time_days": 2.0,
        "lead_time_std": 0.8,
        "avg_basket_size_inr": 420,
        "temp_range": (18, 34),
        "humidity_range": (30, 85),
        "monsoon_months": [],
        "income_segments": {"high": 0.25, "medium": 0.50, "low": 0.25},
        "vegetarian_pct": 0.40,
        "events": [
            {"name": "Dasara", "month": 10, "duration_days": 10, "demand_spike": 2.0,
             "categories": ["sweets", "essentials", "gifting"]},
            {"name": "IPL_RCB", "frequency": "6_matches_home", "demand_spike": 1.6,
             "categories": ["snacks", "beverages"], "month": 4, "duration_days": 2},
            {"name": "Ugadi", "month": 3, "duration_days": 3, "demand_spike": 1.5,
             "categories": ["sweets", "essentials"]},
            {"name": "Diwali", "month": 11, "duration_days": 5, "demand_spike": 2.5,
             "categories": ["sweets", "dry_fruits", "gifting"]},
        ],
    },
    "mumbai": {
        "stores": MUMBAI_STORES,
        "warehouses": MUMBAI_WAREHOUSES,
        "zones": MUMBAI_ZONES,
        "base_demand_multiplier": 1.4,
        "peak_hour_amplification": 1.8,
        "avg_delivery_time_min": 18,
        "rider_speed_kmh_peak": 12,
        "rider_speed_kmh_offpeak": 22,
        "monsoon_speed_penalty": 0.6,
        "avg_lead_time_days": 2.5,
        "lead_time_std": 1.2,
        "monsoon_lead_time_multiplier": 1.5,
        "avg_basket_size_inr": 380,
        "temp_range": (22, 36),
        "humidity_range": (60, 98),
        "monsoon_months": [6, 7, 8, 9],
        "income_segments": {"high": 0.15, "medium": 0.55, "low": 0.30},
        "vegetarian_pct": 0.35,
        "events": [
            {"name": "Ganesh_Chaturthi", "month": 9, "duration_days": 10, "demand_spike": 2.5,
             "categories": ["sweets", "flowers", "essentials"]},
            {"name": "Diwali", "month": 11, "duration_days": 5, "demand_spike": 3.0,
             "categories": ["sweets", "dry_fruits", "gifting"]},
            {"name": "IPL_MI", "frequency": "6_matches_home", "demand_spike": 1.8,
             "categories": ["snacks", "beverages"], "month": 4, "duration_days": 2},
            {"name": "Monsoon_Onset", "month": 6, "duration_days": 90,
             "demand_spike": 1.0, "categories": ["essentials"]},
            {"name": "Navratri", "month": 10, "duration_days": 9, "demand_spike": 1.5,
             "categories": ["fasting_foods"]},
        ],
    },
}


def _generate_suppliers(
    rng: np.random.Generator, city: str, profile: dict[str, Any], n: int = 40,
) -> list[dict[str, Any]]:
    suppliers: list[dict[str, Any]] = []
    prefix = "MUM" if city == "mumbai" else "BLR"
    for i in range(n):
        suppliers.append({
            "id": f"SUP-{prefix}-{i + 1:03d}",
            "name": f"{city.title()} Supplier {i + 1}",
            "lead_time_mean": round(float(np.clip(rng.normal(
                profile["avg_lead_time_days"], profile["lead_time_std"]
            ), 0.5, 7.0)), 2),
            "lead_time_std": round(float(rng.uniform(0.3, profile["lead_time_std"])), 2),
            "reliability_score": round(float(rng.uniform(0.7, 0.98)), 3),
            "monsoon_lead_time_multiplier": profile.get("monsoon_lead_time_multiplier", 1.0),
        })
    return suppliers


def _generate_riders(
    rng: np.random.Generator, city: str, zones: list[dict[str, Any]], n: int = 200,
) -> list[dict[str, Any]]:
    riders: list[dict[str, Any]] = []
    prefix = "MUM" if city == "mumbai" else "BLR"
    zone_names = [z["name"] for z in zones]
    shifts = ["morning", "afternoon", "evening", "night"]
    vehicles = ["bike", "scooter", "cycle"]
    for i in range(n):
        riders.append({
            "id": f"RDR-{prefix}-{i + 1:04d}",
            "name": f"Rider {i + 1}",
            "zone": str(rng.choice(zone_names)),
            "vehicle_type": str(rng.choice(vehicles, p=[0.6, 0.3, 0.1])),
            "shift": str(rng.choice(shifts)),
            "rating": round(float(rng.uniform(3.5, 5.0)), 1),
        })
    return riders


def _is_monsoon_day(d: date, profile: dict[str, Any]) -> bool:
    return d.month in profile.get("monsoon_months", [])


def _monsoon_intensity(d: date, profile: dict[str, Any]) -> float:
    if not _is_monsoon_day(d, profile):
        return 0.0
    if d.month == 6:
        day_of_month = d.day
        return min(0.7 * day_of_month / 30.0, 0.7)
    if d.month == 7:
        return 0.7 + 0.3 * (d.day / 31.0)
    if d.month == 8:
        return 0.6 + 0.3 * (1.0 - d.day / 31.0)
    if d.month == 9:
        return max(0.5 * (1.0 - d.day / 30.0), 0.1)
    return 0.0


def _is_festival_day(d: date, events: list[dict[str, Any]]) -> tuple[bool, str]:
    for ev in events:
        ev_start = date(d.year, ev["month"], 1)
        ev_end = ev_start + timedelta(days=ev["duration_days"])
        if ev_start <= d <= ev_end:
            return True, ev["name"]
    return False, ""


def _generate_demand_history(
    rng: np.random.Generator,
    stores: list[dict[str, Any]],
    skus: list[dict[str, Any]],
    profile: dict[str, Any],
    n_days: int,
    start_date: date,
) -> pd.DataFrame:
    log.info("generating_demand_history", stores=len(stores), skus=len(skus), days=n_days)
    records: list[dict[str, Any]] = []
    events = profile.get("events", [])
    base_mult = profile["base_demand_multiplier"]

    for day_offset in range(n_days):
        d = start_date + timedelta(days=day_offset)
        is_wknd = d.weekday() >= 5
        is_monsoon = _is_monsoon_day(d, profile)
        is_fest, fest_name = _is_festival_day(d, events)

        for store in stores:
            zone_rng_factor = rng.uniform(0.8, 1.2)
            for sku in skus:
                base_demand = max(1, int(rng.poisson(5 * base_mult * zone_rng_factor)))
                if is_wknd:
                    base_demand = int(base_demand * rng.uniform(0.8, 1.3))
                if is_monsoon:
                    if sku.get("is_essential", False):
                        base_demand = int(base_demand * rng.uniform(1.1, 1.4))
                    else:
                        base_demand = int(base_demand * rng.uniform(0.6, 0.9))
                if is_fest:
                    base_demand = int(base_demand * rng.uniform(1.2, 2.0))

                temp = rng.uniform(*profile["temp_range"])
                humidity = rng.uniform(*profile["humidity_range"])
                precip = 0.0
                if is_monsoon:
                    precip = float(rng.exponential(20.0))

                records.append({
                    "date": d.isoformat(),
                    "store_id": store["id"],
                    "sku_id": sku["sku_id"],
                    "quantity": max(0, base_demand),
                    "hour": int(rng.choice([8, 9, 10, 11, 12, 18, 19, 20, 21])),
                    "day_of_week": d.weekday(),
                    "is_weekend": is_wknd,
                    "is_festival": is_fest,
                    "festival_name": fest_name if is_fest else "",
                    "temperature_c": round(temp, 1),
                    "humidity_pct": round(humidity, 1),
                    "precip_mm": round(precip, 1),
                    "monsoon_active": is_monsoon,
                })

        if day_offset % 10 == 0:
            log.info("demand_progress", day=day_offset, total=n_days)

    return pd.DataFrame(records)


def _generate_weather_history(
    rng: np.random.Generator,
    stores: list[dict[str, Any]],
    profile: dict[str, Any],
    n_days: int,
    start_date: date,
) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    for day_offset in range(n_days):
        d = start_date + timedelta(days=day_offset)
        m_intensity = _monsoon_intensity(d, profile)
        for store in stores:
            temp = rng.uniform(*profile["temp_range"])
            humidity = rng.uniform(*profile["humidity_range"])
            precip = 0.0
            precip_prob = 0.1
            wind = rng.uniform(5, 20)
            visibility = rng.uniform(5, 15)

            if m_intensity > 0:
                precip = float(rng.exponential(30.0 * m_intensity))
                precip_prob = min(0.3 + m_intensity * 0.6, 1.0)
                humidity = min(humidity + m_intensity * 15, 99.0)
                wind = rng.uniform(10, max(60 * m_intensity, 11.0))
                visibility = max(rng.uniform(0.5, 10) * (1 - m_intensity), 0.3)

            records.append({
                "date": d.isoformat(),
                "store_id": store["id"],
                "temperature_c": round(temp, 1),
                "humidity_pct": round(humidity, 1),
                "precip_mm": round(precip, 1),
                "wind_speed_kmh": round(wind, 1),
                "precip_prob": round(precip_prob, 2),
                "monsoon_intensity": round(m_intensity, 2),
                "visibility_km": round(visibility, 1),
            })
    return pd.DataFrame(records)


def generate_city(city: str, n_stores: int, n_days: int, seed: int, output_dir: str) -> None:
    rng = np.random.default_rng(seed)
    profile = CITY_PROFILES[city]
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    stores = profile["stores"][:n_stores]
    warehouses = profile["warehouses"]
    zones = profile["zones"]

    skus = _generate_sku_catalog(rng, 500)
    suppliers = _generate_suppliers(rng, city, profile)
    riders = _generate_riders(rng, city, zones)
    events = profile.get("events", [])

    # Mumbai start date covers monsoon months (Jun-Sep) for monsoon_intensity (E-S6-09).
    # Bengaluru has no monsoon months defined, so January is fine.
    start_date = date(2025, 6, 1) if city == "mumbai" else date(2025, 1, 1)

    # Write JSON files
    for name, data in [
        ("stores", stores),
        ("warehouses", warehouses),
        ("suppliers", suppliers),
        ("zones", zones),
        ("riders", riders),
        ("skus", skus),
        ("events", events),
    ]:
        path = out / f"{name}.json"
        path.write_text(json.dumps(data, indent=2, sort_keys=True))
        log.info("wrote_json", file=str(path), count=len(data))

    # Generate demand history CSV
    demand_df = _generate_demand_history(rng, stores, skus, profile, n_days, start_date)
    demand_path = out / "demand_history.csv"
    demand_df.to_csv(demand_path, index=False)
    log.info("wrote_demand_history", file=str(demand_path), rows=len(demand_df))

    # Generate weather history CSV
    weather_df = _generate_weather_history(rng, stores, profile, n_days, start_date)
    weather_path = out / "weather_history.csv"
    weather_df.to_csv(weather_path, index=False)
    log.info("wrote_weather_history", file=str(weather_path), rows=len(weather_df))

    log.info("city_generation_complete", city=city, output_dir=str(out))


def main() -> None:
    parser = argparse.ArgumentParser(description="SYNAPSE City Data Generator")
    parser.add_argument("--city", required=True, choices=["bengaluru", "mumbai"])
    parser.add_argument("--stores", type=int, default=25)
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-dir", type=str, default=None)
    args = parser.parse_args()

    output_dir = args.output_dir or f"data/{args.city}"
    generate_city(args.city, args.stores, args.days, args.seed, output_dir)


if __name__ == "__main__":
    main()
