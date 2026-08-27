"""M1 — Efficiency Audit: MFU/MBU, the GPU-Util lie, and idle waste (deck §5).

Run: python missions/m1_efficiency_audit.py
"""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from collections import defaultdict
from missions._common import load_csv, num, catalog_by_type
from finops import metrics


def run(verbose: bool = True) -> dict:
    tel = load_csv("gpu_telemetry.csv")
    cat = catalog_by_type()

    # per-row MFU/MBU, then aggregate per GPU
    agg = defaultdict(lambda: {"util": [], "mfu": [], "mbu": [], "type": None, "idle_hours": 0})
    for r in tel:
        gtype = r["gpu_type"]
        peak_fp16 = num(cat[gtype]["peak_tflops_fp16"])
        peak_bw = num(cat[gtype]["peak_bw_tbs"])
        mfu = metrics.compute_mfu(num(r["achieved_tflops"]), peak_fp16)
        mbu = metrics.compute_mbu(num(r["achieved_bw_tbs"]), peak_bw)
        a = agg[r["gpu_id"]]
        a["type"] = gtype
        a["util"].append(num(r["gpu_util_pct"]))
        a["mfu"].append(mfu)
        a["mbu"].append(mbu)
        if num(r["gpu_util_pct"]) < 10:  # effectively idle this interval (1h)
            a["idle_hours"] += 1

    summary = []
    for gid, a in agg.items():
        summary.append({
            "gpu_id": gid, "gpu_type": a["type"],
            "gpu_util_pct": round(sum(a["util"]) / len(a["util"]), 1),
            "mfu": round(sum(a["mfu"]) / len(a["mfu"]), 3),
            "mbu": round(sum(a["mbu"]) / len(a["mbu"]), 3),
            "idle_hours": a["idle_hours"],
        })

    lies = metrics.flag_util_lies(summary)
    idle_waste = 0.0
    for s in summary:
        on_demand = num(catalog_by_type()[s["gpu_type"]]["on_demand_hr"])
        idle_waste += metrics.idle_waste_usd(s["idle_hours"], on_demand)

    # Extension 2: Right-sizing memory-bound GPUs based on MBU and $/GB-VRAM
    rightsize_recs = []
    total_mbu_rightsize_monthly_savings = 0.0
    for s in summary:
        gtype = s["gpu_type"]
        peak_bw = num(cat[gtype]["peak_bw_tbs"])
        achieved_bw = peak_bw * s["mbu"]
        # If GPU has low MFU/MBU and is memory-bound or low utilization
        rec = metrics.recommend_mbu_rightsizing(gtype, cat, achieved_bw)
        if rec:
            monthly_sav = rec["hourly_savings"] * (24 - s["idle_hours"]) * 30
            total_mbu_rightsize_monthly_savings += monthly_sav
            rightsize_recs.append({**rec, "gpu_id": s["gpu_id"], "monthly_savings": round(monthly_sav, 2)})

    if verbose:
        print("== M1 Efficiency Audit ==")
        print(f"{'GPU':14}{'type':7}{'util%':>7}{'MFU':>7}{'MBU':>7}{'idle_h':>8}")
        for s in sorted(summary, key=lambda x: x["mfu"]):
            print(f"{s['gpu_id']:14}{s['gpu_type']:7}{s['gpu_util_pct']:>7}{s['mfu']:>7}{s['mbu']:>7}{s['idle_hours']:>8}")
        print(f"\nGPU-Util LIES (util>=90% but MFU<30%): {[l['gpu_id'] for l in lies]}")
        print(f"Idle waste (1 day): ${idle_waste:,.2f}  ->  ${idle_waste*30:,.0f}/month")
        
        print("\n--- Extension 2: VRAM Unit Economics & MBU Right-Sizing ---")
        print(f"{'GPU Type':10}{'$/hr':>8}{'VRAM(GB)':>10}{'$/GB-hr':>12}{'Peak BW (TB/s)':>16}")
        for gt, row in cat.items():
            cost_vram = metrics.cost_per_gb_vram(num(row["on_demand_hr"]), num(row["hbm_gb"]))
            print(f"{gt:10}${num(row['on_demand_hr']):>7.2f}{num(row['hbm_gb']):>10.0f}${cost_vram:>11.4f}{num(row['peak_bw_tbs']):>16.2f}")
        
        if rightsize_recs:
            print("\nRecommended MBU Right-Sizing:")
            for r in rightsize_recs:
                print(f"  {r['gpu_id']} ({r['current_type']} -> {r['target_type']}): Save ${r['hourly_savings']:.2f}/hr (~${r['monthly_savings']:,.0f}/mo, -{r['savings_pct']}%)")
            print(f"Total potential monthly right-sizing savings: ${total_mbu_rightsize_monthly_savings:,.0f}/month")

    return {
        "summary": summary,
        "lies": lies,
        "idle_waste_daily": round(idle_waste, 2),
        "mbu_rightsize_recs": rightsize_recs,
        "mbu_rightsize_monthly_savings": round(total_mbu_rightsize_monthly_savings, 2),
    }


if __name__ == "__main__":
    run()
