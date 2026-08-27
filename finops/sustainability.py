"""Sustainability economics — energy and carbon as governed cost levers (deck §11).

Region selection cuts $ and carbon together; reasoning queries are an energy bomb.
"""
from __future__ import annotations

# Grid carbon intensity (gCO2 / kWh) — illustrative 2026 snapshot.
REGION_CARBON = {
    "us-east-1": 380,
    "us-west-2": 120,   # Oregon hydro
    "europe-north1": 30,  # Norway
    "europe-central2": 660,  # Poland (dirtiest)
    "us-east-wa": 90,
}
# Electricity price (USD / kWh) — illustrative.
REGION_PRICE_KWH = {
    "us-east-1": 0.12,
    "us-west-2": 0.07,
    "europe-north1": 0.09,
    "europe-central2": 0.18,
    "us-east-wa": 0.055,
}

REASONING_ENERGY_MULTIPLIER = 80.0  # deck: reasoning ~74-86x a small-model query


def wh_per_query(total_tokens: int, wh_per_1k_tokens: float = 0.30, is_reasoning: bool = False) -> float:
    """Energy for one query. Median Gemini prompt ~0.24 Wh; reasoning ~74-86x."""
    base = (total_tokens / 1000.0) * wh_per_1k_tokens
    return base * (REASONING_ENERGY_MULTIPLIER if is_reasoning else 1.0)


def carbon_g(wh: float, region: str = "us-east-1") -> float:
    """Grams CO2 for an energy amount in a region."""
    gco2_kwh = REGION_CARBON.get(region, 400)
    return (wh / 1000.0) * gco2_kwh


def energy_cost_usd(wh: float, region: str = "us-east-1") -> float:
    """Electricity cost of an energy amount in a region."""
    return (wh / 1000.0) * REGION_PRICE_KWH.get(region, 0.12)


def tokens_per_watt(total_tokens: int, wh: float, seconds: float = 1.0) -> float:
    """Energy efficiency of serving: tokens per watt (higher is better)."""
    watts = (wh * 3600.0) / seconds if seconds > 0 else 0.0
    return total_tokens / watts if watts > 0 else 0.0


def region_cost_and_carbon_matrix(wh: float) -> list[dict]:
    """Generate comparative matrix of carbon emissions and electricity cost across all regions."""
    out = []
    for reg in REGION_CARBON:
        c_g = carbon_g(wh, reg)
        cost = energy_cost_usd(wh, reg)
        out.append({
            "region": reg,
            "carbon_g": round(c_g, 2),
            "electricity_cost_usd": round(cost, 4),
            "carbon_intensity_g_kwh": REGION_CARBON[reg],
            "electricity_price_kwh": REGION_PRICE_KWH[reg],
        })
    return out


def carbon_aware_schedule(
    total_energy_wh: float,
    baseline_region: str = "us-east-1",
    target_region: str = "europe-north1",
) -> dict:
    """Calculate carbon and electricity cost reduction when migrating workloads to a greener region."""
    base_carbon = carbon_g(total_energy_wh, baseline_region)
    target_carbon = carbon_g(total_energy_wh, target_region)
    carbon_saved = base_carbon - target_carbon
    carbon_reduction_pct = (carbon_saved / base_carbon * 100.0) if base_carbon > 0 else 0.0

    base_cost = energy_cost_usd(total_energy_wh, baseline_region)
    target_cost = energy_cost_usd(total_energy_wh, target_region)
    cost_saved = base_cost - target_cost

    return {
        "baseline_region": baseline_region,
        "target_region": target_region,
        "energy_kwh": round(total_energy_wh / 1000.0, 2),
        "baseline_carbon_kg": round(base_carbon / 1000.0, 2),
        "target_carbon_kg": round(target_carbon / 1000.0, 2),
        "carbon_saved_kg": round(carbon_saved / 1000.0, 2),
        "carbon_reduction_pct": round(carbon_reduction_pct, 1),
        "baseline_cost_usd": round(base_cost, 2),
        "target_cost_usd": round(target_cost, 2),
        "cost_saved_usd": round(cost_saved, 2),
    }

