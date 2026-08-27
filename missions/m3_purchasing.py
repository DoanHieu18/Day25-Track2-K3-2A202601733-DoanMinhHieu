"""M3 — Purchasing Strategy: break-even, tier choice, spot-checkpoint sim (deck §4).

Run: python missions/m3_purchasing.py
"""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from missions._common import load_csv, num, catalog_by_type
from finops import pricing

DAYS = 30


def run(verbose: bool = True) -> dict:
    jobs = load_csv("workloads.csv")
    cat = catalog_by_type()
    on_demand_monthly = optimized_monthly = 0.0
    recs = []
    for j in jobs:
        gtype = j["gpu_type"]
        ngpu = int(num(j["num_gpus"]))
        hpd = num(j["hours_per_day"])
        interruptible = bool(int(num(j["interruptible"])))
        c = cat[gtype]
        gpu_hours = hpd * DAYS * ngpu
        od = num(c["on_demand_hr"])
        on_demand_cost = gpu_hours * od

        tier = pricing.recommend_tier(hpd, interruptible)
        if tier == "spot":
            sim = pricing.spot_checkpoint_cost(gpu_hours, num(c["spot_hr"]), od)
            opt_cost = sim["spot_cost"]
        elif tier == "reserved":
            opt_cost = gpu_hours * num(c["reserved_3yr_hr"])
        else:
            opt_cost = on_demand_cost

        on_demand_monthly += on_demand_cost
        optimized_monthly += opt_cost
        recs.append({"job_id": j["job_id"], "gpu_type": gtype, "tier": tier,
                     "on_demand": round(on_demand_cost), "optimized": round(opt_cost)})

    savings = on_demand_monthly - optimized_monthly
    savings_pct = savings / on_demand_monthly * 100 if on_demand_monthly else 0.0

    # Extension 5: Carbon-aware scheduling for interruptible workloads
    from finops import sustainability
    interruptible_energy_wh = 0.0
    for j in jobs:
        if bool(int(num(j["interruptible"]))):
            gtype = j["gpu_type"]
            ngpu = int(num(j["num_gpus"]))
            hpd = num(j["hours_per_day"])
            days = num(j["days"])
            watts = num(cat[gtype]["watts"])
            interruptible_energy_wh += watts * hpd * days * ngpu

    carbon_schedule = sustainability.carbon_aware_schedule(
        interruptible_energy_wh,
        baseline_region="us-east-1",
        target_region="europe-north1"
    )
    reg_matrix = sustainability.region_cost_and_carbon_matrix(interruptible_energy_wh)

    if verbose:
        print("== M3 Purchasing Strategy ==")
        print(f"break-even utilization @ 45% reserved discount = {pricing.break_even_utilization(0.45):.0%}")
        print(f"{'job':18}{'gpu':7}{'tier':11}{'on-demand':>12}{'optimized':>12}")
        for r in recs:
            print(f"{r['job_id']:18}{r['gpu_type']:7}{r['tier']:11}${r['on_demand']:>11,}${r['optimized']:>11,}")
        print(f"\nmonthly: on-demand ${on_demand_monthly:,.0f} -> optimized ${optimized_monthly:,.0f}  ({savings_pct:.1f}% saved)")

        print("\n--- Extension 5: Carbon-Aware Scheduling (Interruptible Workloads) ---")
        print(f"Total Interruptible Compute Energy: {carbon_schedule['energy_kwh']:,.1f} kWh")
        print(f"{'Region':18}{'Carbon (g/kWh)':>16}{'Total CO2 (kg)':>16}{'Elec Cost ($)':>16}")
        for rm in reg_matrix:
            print(f"{rm['region']:18}{rm['carbon_intensity_g_kwh']:>16}{rm['carbon_g']/1000:>16.1f}${rm['electricity_cost_usd']:>15.2f}")
        print(f"\nShifting us-east-1 -> europe-north1 saves {carbon_schedule['carbon_saved_kg']:,.1f} kg CO2e ({carbon_schedule['carbon_reduction_pct']}%) & saves ${carbon_schedule['cost_saved_usd']:.2f} electricity cost.")

    return {
        "recommendations": recs,
        "on_demand_monthly": round(on_demand_monthly),
        "optimized_monthly": round(optimized_monthly),
        "savings_pct": round(savings_pct, 1),
        "carbon_schedule": carbon_schedule,
        "region_matrix": reg_matrix,
    }


if __name__ == "__main__":
    run()
