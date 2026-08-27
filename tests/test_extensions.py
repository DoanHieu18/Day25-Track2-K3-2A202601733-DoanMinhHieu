import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from finops import pricing, metrics, sustainability


def test_cache_is_worth_it():
    # Write cost = $3.0/1M, Read saving per query = $3.0 * (1 - 0.10) = $2.70/1M
    # 1 read: total saving = $2.70 < $3.00 write cost -> False
    assert pricing.cache_is_worth_it(avg_cache_reads=1.0, write_cost_per_m=3.0, read_discount=0.10) is False
    # 2 reads: total saving = $5.40 > $3.00 write cost -> True
    assert pricing.cache_is_worth_it(avg_cache_reads=2.0, write_cost_per_m=3.0, read_discount=0.10) is True
    # Edge case: 0 reads
    assert pricing.cache_is_worth_it(avg_cache_reads=0.0, write_cost_per_m=3.0) is False


def test_recommend_tier_extended():
    # Backward compatibility
    assert pricing.recommend_tier(20, True) == "spot"
    assert pricing.recommend_tier(24, False) == "reserved"
    assert pricing.recommend_tier(5, False) == "on_demand"
    # With extended keyword args
    assert pricing.recommend_tier(hours_per_day=24, interruptible=False, gpu_type="H100", job_days=30) == "reserved"


def test_cost_per_gb_vram():
    assert abs(metrics.cost_per_gb_vram(2.50, 80) - 0.03125) < 1e-6
    assert metrics.cost_per_gb_vram(1.0, 0) == 0.0


def test_recommend_mbu_rightsizing():
    mock_catalog = {
        "H100": {"on_demand_hr": 2.50, "peak_bw_tbs": 3.35, "hbm_gb": 80},
        "A100": {"on_demand_hr": 1.79, "peak_bw_tbs": 2.00, "hbm_gb": 80},
        "A10G": {"on_demand_hr": 1.00, "peak_bw_tbs": 0.60, "hbm_gb": 24},
    }
    # If a workload on H100 only achieves 0.5 TB/s bandwidth, A100 (peak 2.0 TB/s * 0.6 = 1.2 TB/s >= 0.5) or A10G (0.6 * 0.6 = 0.36 < 0.5)
    rec = metrics.recommend_mbu_rightsizing("H100", mock_catalog, achieved_bw_tbs=0.5, target_mbu=0.60)
    assert rec is not None
    assert rec["target_type"] == "A100"
    assert rec["hourly_savings"] == round(2.50 - 1.79, 2)


def test_sustainability_matrix_and_schedule():
    matrix = sustainability.region_cost_and_carbon_matrix(10000)  # 10 kWh
    assert len(matrix) == len(sustainability.REGION_CARBON)
    sched = sustainability.carbon_aware_schedule(10000, baseline_region="us-east-1", target_region="europe-north1")
    assert sched["carbon_saved_kg"] > 0
    assert sched["carbon_reduction_pct"] > 80  # Norway is ~30 g vs US East ~380 g
