"""M2 — Inference Cost Levers: $/1M-token, batch x cache x cascade (deck §7).

Run: python missions/m2_inference_levers.py
"""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from missions._common import load_csv, num
from finops import pricing

# $/1M tokens (input, output) — illustrative 2026.
MODEL_PRICES = {"small": (0.20, 0.40), "large": (3.00, 15.00)}


def run(verbose: bool = True) -> dict:
    rows = load_csv("token_usage.csv")
    base_cost = opt_cost = 0.0
    total_tokens = 0
    for r in rows:
        inp, out = int(num(r["input_tokens"])), int(num(r["output_tokens"]))
        cached = int(num(r["cached_input_tokens"]))
        is_batch = bool(int(num(r["is_batch"])))
        total_tokens += inp + out
        # BASELINE: naive deployment — everything on the large model, no cache, no batch
        lin, lout = MODEL_PRICES["large"]
        base_cost += pricing.request_cost(inp, out, lin, lout)
        # OPTIMIZED: cascade (route_tier), prompt caching, batch API
        pin, pout = MODEL_PRICES[r["route_tier"]]
        opt_cost += pricing.request_cost(inp, out, pin, pout, cached_in=cached, batch=is_batch)

    base_pm = pricing.dollars_per_million(base_cost, total_tokens)
    opt_pm = pricing.dollars_per_million(opt_cost, total_tokens)
    savings_pct = (1 - opt_cost / base_cost) * 100 if base_cost else 0.0

    # Individual lever attribution
    cascade_only_cost = 0.0
    cache_only_cost = 0.0
    batch_only_cost = 0.0
    
    # Extension 4: Reasoning budget analysis
    reasoning_reqs = 0
    non_reasoning_reqs = 0
    reasoning_tokens = 0
    non_reasoning_tokens = 0
    reasoning_cost = 0.0
    non_reasoning_cost = 0.0

    total_cached_toks = 0
    total_input_toks = 0

    for r in rows:
        inp, out = int(num(r["input_tokens"])), int(num(r["output_tokens"]))
        cached = int(num(r["cached_input_tokens"]))
        is_batch = bool(int(num(r["is_batch"])))
        is_reasoning = bool(int(num(r["is_reasoning"])))
        lin, lout = MODEL_PRICES["large"]
        pin, pout = MODEL_PRICES[r["route_tier"]]

        total_cached_toks += cached
        total_input_toks += inp

        # Cascade only
        cascade_only_cost += pricing.request_cost(inp, out, pin, pout)
        # Cache only
        cache_only_cost += pricing.request_cost(inp, out, lin, lout, cached_in=cached)
        # Batch only
        batch_only_cost += pricing.request_cost(inp, out, lin, lout, batch=is_batch)

        req_opt_cost = pricing.request_cost(inp, out, pin, pout, cached_in=cached, batch=is_batch)
        if is_reasoning:
            reasoning_reqs += 1
            reasoning_tokens += (inp + out)
            reasoning_cost += req_opt_cost
        else:
            non_reasoning_reqs += 1
            non_reasoning_tokens += (inp + out)
            non_reasoning_cost += req_opt_cost

    # Extension 3: Cache is worth it analysis
    # Assuming average cached prefix is read ~3-5 times in production chat/rag
    avg_reads_estimate = 4.0
    cache_worth_small = pricing.cache_is_worth_it(avg_reads_estimate, write_cost_per_m=MODEL_PRICES["small"][0], read_discount=0.10)
    cache_worth_large = pricing.cache_is_worth_it(avg_reads_estimate, write_cost_per_m=MODEL_PRICES["large"][0], read_discount=0.10)
    avg_cache_hit_rate = (total_cached_toks / total_input_toks) if total_input_toks else 0.0

    if verbose:
        print("== M2 Inference Cost Levers ==")
        print(f"requests={len(rows)}  tokens={total_tokens:,}")
        print(f"baseline  : ${base_cost:,.2f}/day   ${base_pm:.3f}/1M-token")
        print(f"optimized : ${opt_cost:,.2f}/day   ${opt_pm:.3f}/1M-token")
        print(f"savings   : {savings_pct:.1f}%  (cascade + caching + batch)")
        print(f"discount stack (batch + 100% cache): {pricing.discount_stack(batch=True, cache_hit_frac=1.0):.3f} of naive")
        
        print("\n--- Lever Breakdown (Individual Savings vs Baseline) ---")
        print(f"  Cascade alone : ${base_cost - cascade_only_cost:8.2f}/day ({(1 - cascade_only_cost/base_cost)*100:.1f}% saved)")
        print(f"  Cache alone   : ${base_cost - cache_only_cost:8.2f}/day ({(1 - cache_only_cost/base_cost)*100:.1f}% saved)")
        print(f"  Batch alone   : ${base_cost - batch_only_cost:8.2f}/day ({(1 - batch_only_cost/base_cost)*100:.1f}% saved)")

        print("\n--- Extension 3: Prompt Caching Economics ---")
        print(f"  Dataset cache hit rate: {avg_cache_hit_rate:.1%} of input tokens")
        print(f"  Cache worth it (Small Tier @ {avg_reads_estimate:.0f} reads): {cache_worth_small}")
        print(f"  Cache worth it (Large Tier @ {avg_reads_estimate:.0f} reads): {cache_worth_large}")
        print(f"  Break-even read multiplier: > {1.0 / (1.0 - 0.10):.2f}x reads required to offset write storage overhead")

        print("\n--- Extension 4: Reasoning Budget Analysis ---")
        print(f"  Reasoning Requests     : {reasoning_reqs:4d} ({reasoning_reqs/len(rows):.1%}) | Tokens: {reasoning_tokens:,} ({reasoning_tokens/total_tokens:.1%}) | Cost: ${reasoning_cost:.2f}/day ({reasoning_cost/opt_cost:.1%})")
        print(f"  Non-Reasoning Requests : {non_reasoning_reqs:4d} ({non_reasoning_reqs/len(rows):.1%}) | Tokens: {non_reasoning_tokens:,} ({non_reasoning_tokens/total_tokens:.1%}) | Cost: ${non_reasoning_cost:.2f}/day ({non_reasoning_cost/opt_cost:.1%})")
        print(f"  Cost per 1M-token Reasoning     : ${pricing.dollars_per_million(reasoning_cost, reasoning_tokens):.3f}")
        print(f"  Cost per 1M-token Non-Reasoning : ${pricing.dollars_per_million(non_reasoning_cost, non_reasoning_tokens):.3f}")

    return {
        "baseline_daily": round(base_cost, 2), "optimized_daily": round(opt_cost, 2),
        "baseline_per_m": round(base_pm, 3), "optimized_per_m": round(opt_pm, 3),
        "savings_pct": round(savings_pct, 1), "total_tokens": total_tokens,
        "lever_breakdown": {
            "cascade_savings_daily": round(base_cost - cascade_only_cost, 2),
            "cache_savings_daily": round(base_cost - cache_only_cost, 2),
            "batch_savings_daily": round(base_cost - batch_only_cost, 2),
        },
        "reasoning_analysis": {
            "reasoning_reqs": reasoning_reqs,
            "reasoning_cost_daily": round(reasoning_cost, 2),
            "reasoning_tokens": reasoning_tokens,
            "non_reasoning_cost_daily": round(non_reasoning_cost, 2),
            "non_reasoning_tokens": non_reasoning_tokens,
        },
        "cache_economics": {
            "cache_hit_rate": round(avg_cache_hit_rate, 3),
            "break_even_reads": 1.11,
            "is_worth_it": cache_worth_small and cache_worth_large,
        }
    }


if __name__ == "__main__":
    run()
