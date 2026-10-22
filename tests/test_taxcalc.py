"""The tests use explicit, simple rules (not the illustrative defaults), so the arithmetic can be checked by hand."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from taxcalc import BudgetExceeded, CostCap, Rules, best_form, compare, compute, costs_break_even, required_revenue  # noqa: E402

R = Rules(ryczalt_rate=0.12, flat_rate=0.19, flat_health_rate=0.05, flat_health_deduction_limit=10000, scale_low=0.12, scale_high=0.32, scale_threshold=100000,
          scale_tax_free_reduction=3000, scale_health_rate=0.09, social_monthly={"start": 0.0, "preferential": 500.0, "full": 2000.0},
          health_ryczalt_monthly={"up_to_60k": 400.0, "up_to_300k": 700.0, "over_300k": 1300.0}, health_minimum_monthly=300.0)
FULL = {"start": 0, "preferential": 0, "full": 12}
PREF = {"start": 0, "preferential": 12, "full": 0}


def test_ryczalt_by_hand():
    # revenue 120000, social 12*2000=24000, health (60k-300k bracket) 12*700=8400
    # tax = 0.12*(120000-24000) - 0.5*8400 = 11520 - 4200 = 7320 ; net = 120000 - 0 - 24000 - 8400 - 7320 = 80280
    r = compute(120000, 0, "ryczalt", R, FULL)
    assert (r["social"], r["health"], r["tax"], r["net_year"], r["net_month"]) == (24000.0, 8400.0, 7320.0, 80280.0, 6690.0)


def test_flat_by_hand():
    # income 120000-40000 costs = 80000 ; social 24000 ; health = 5% * (80000-24000) = 2800 (above the 12*300 minimum 3600? no: minimum wins)
    r = compute(120000, 40000, "flat", R, FULL)
    assert r["health"] == 3600.0                                   # the legal minimum is higher than 5% of 56000
    assert r["tax"] == round(0.19 * (80000 - 24000 - 3600)) == 9956.0
    assert r["net_year"] == 120000 - 40000 - 24000 - 3600 - 9956


def test_scale_by_hand_with_both_brackets_and_the_tax_free_reduction():
    # income 200000, social 24000 -> base 176000 ; tax = 0.12*100000 + 0.32*76000 - 3000 = 12000 + 24320 - 3000 = 33320
    r = compute(200000, 0, "scale", R, FULL)
    assert r["tax"] == 33320.0 and r["health"] == pytest.approx(0.09 * 176000)
    assert compute(10000, 0, "scale", R, PREF)["tax"] == 0.0        # a tiny base: the reduction wipes the tax out, it never goes negative


def test_ryczalt_tax_never_goes_negative_and_a_loss_pays_no_flat_tax():
    assert compute(20000, 0, "ryczalt", R, FULL)["tax"] == 0.0
    r = compute(10000, 30000, "flat", R, PREF)
    assert r["tax"] == 0.0 and r["health"] == 0.0


def test_start_relief_months_reduce_social_contributions():
    mixed = {"start": 6, "preferential": 6, "full": 0}
    assert compute(100000, 0, "ryczalt", R, mixed)["social"] == 6 * 500.0
    assert compute(100000, 0, "ryczalt", R, mixed)["net_year"] > compute(100000, 0, "ryczalt", R, FULL)["net_year"]


def test_invalid_input_is_refused():
    for args in ((-1, 0, "ryczalt", R, FULL), (100, 0, "ryczalt", R, {"start": 0, "preferential": 0, "full": 11}), (100, 0, "magic", R, FULL), (100, 0, "flat", R, {"x": 12})):
        with pytest.raises(ValueError):
            compute(*args)


def test_the_rule_of_thumb_flat_wins_only_when_costs_are_high():
    low, high = compare(120000, 5000, R, FULL), compare(120000, 70000, R, FULL)
    assert max(low, key=lambda f: low[f]["net_year"]) == "ryczalt"
    assert compute(120000, 70000, "flat", R, FULL)["net_year"] > compute(120000, 70000, "ryczalt", R, FULL)["net_year"]
    assert best_form(120000, 70000, R, FULL) == "scale"                          # at a low income the scale (with its tax-free reduction) beats both
    assert best_form(400000, 150000, R, FULL) == "flat"                          # at a high income the flat tax is the best of the three
    be = costs_break_even(120000, R, FULL)
    assert 5000 < be < 70000
    assert compute(120000, be, "flat", R, FULL)["net_year"] > compute(120000, be, "ryczalt", R, FULL)["net_year"]
    assert compute(120000, be - 500, "flat", R, FULL)["net_year"] <= compute(120000, be - 500, "ryczalt", R, FULL)["net_year"]


@pytest.mark.parametrize("form", ["ryczalt", "flat", "scale"])
def test_required_revenue_hits_the_target_net(form):
    rev = required_revenue(5100, 6000, form, R, FULL)
    assert compute(rev, 6000, form, R, FULL)["net_month"] == pytest.approx(5100, abs=0.5)
    assert compute(rev - 100, 6000, form, R, FULL)["net_month"] < 5100          # and it is the smallest such revenue, not just any


def test_required_revenue_is_lower_with_relief_contributions_and_rejects_impossible_targets():
    assert required_revenue(5100, 0, "ryczalt", R, PREF) < required_revenue(5100, 0, "ryczalt", R, FULL)
    with pytest.raises(ValueError):
        required_revenue(10_000_000, 0, "ryczalt", R, FULL)


# ---------------------------------------------------------------- cost cap
def test_a_job_may_spend_only_its_share_of_the_revenue_and_a_refused_charge_is_not_recorded():
    cap = CostCap(monthly_ceiling=1000)
    cap.add_job("data entry", monthly_revenue=400, max_share=0.25)              # limit 100
    assert cap.charge("data entry", 60) == "ok"
    assert cap.charge("data entry", 25) == "warning"                            # 85 of 100: past the 80% warning line
    with pytest.raises(BudgetExceeded, match="exceed its limit of 100.00"):
        cap.charge("data entry", 16)
    assert cap.jobs["data entry"].spent == 85 and cap.jobs["data entry"].remaining == 15
    assert cap.charge("data entry", 15) == "warning"


def test_the_fleet_ceiling_stops_spending_even_when_each_job_is_within_its_own_limit():
    cap = CostCap(monthly_ceiling=150)
    cap.add_job("a", 1000, 0.5)
    cap.add_job("b", 1000, 0.5)
    cap.charge("a", 100)
    with pytest.raises(BudgetExceeded, match="monthly ceiling"):
        cap.charge("b", 60)
    cap.charge("b", 50)
    assert cap.total_spent == 150


def test_report_shows_state_and_profit_before_tax_and_input_is_validated():
    cap = CostCap(500)
    cap.add_job("x", 200, 0.5)
    cap.charge("x", 90)
    rep = cap.report()[0]
    assert rep == {"job": "x", "revenue": 200, "spent": 90.0, "limit": 100.0, "profit_before_tax": 110.0, "state": "warning"}
    for bad in (("x", 100, 0.2), ("y", 0, 0.2), ("y", 100, 0), ("y", 100, 1.5)):
        with pytest.raises(ValueError):
            cap.add_job(*bad)
    with pytest.raises(ValueError):
        cap.charge("x", -1)
