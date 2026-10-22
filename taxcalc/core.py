"""Compares the three Polish income-tax forms for a sole proprietorship (flat-rate ryczalt, flat 19% and the progressive scale) including
social and health contributions, and answers the question "how much must I invoice to keep N zloty per month?".

IMPORTANT: every number that changes by law or by year (rates, thresholds, contribution amounts) lives in `Rules` and the defaults below are
ASSUMED values for illustration. They are NOT guaranteed to be current: pass the real figures for the year (from ZUS and the tax office, or
from your accountant). The calculation logic is tested with explicit rules, independent of the defaults. This is a planning aid, not tax advice."""
from dataclasses import dataclass, field
from typing import Dict


@dataclass
class Rules:
    # ryczalt: tax = rate * (revenue - social contributions paid) - 50% of health contributions paid
    ryczalt_rate: float = 0.12
    # liniowy
    flat_rate: float = 0.19
    flat_health_rate: float = 0.049
    flat_health_deduction_limit: float = 11600.0
    # scale
    scale_low: float = 0.12
    scale_high: float = 0.32
    scale_threshold: float = 120000.0
    scale_tax_free_reduction: float = 3600.0
    scale_health_rate: float = 0.09
    # contributions per month (ASSUMED, check the current year)
    social_monthly: Dict[str, float] = field(default_factory=lambda: {"start": 0.0, "preferential": 500.0, "full": 1900.0})
    health_ryczalt_monthly: Dict[str, float] = field(default_factory=lambda: {"up_to_60k": 470.0, "up_to_300k": 780.0, "over_300k": 1400.0})
    health_minimum_monthly: float = 432.0


def _health_ryczalt(revenue: float, r: Rules) -> float:
    key = "up_to_60k" if revenue <= 60000 else "up_to_300k" if revenue <= 300000 else "over_300k"
    return r.health_ryczalt_monthly[key] * 12


def compute(revenue: float, costs: float, form: str, rules: Rules, months: Dict[str, int]) -> Dict[str, float]:
    """revenue and costs for the YEAR; months = how many months of {start, preferential, full} contributions (sum 12). Returns the yearly figures."""
    if revenue < 0 or costs < 0 or sum(months.values()) != 12 or set(months) - set(rules.social_monthly):
        raise ValueError("revenue and costs must be >= 0 and the months must add up to 12 over the keys %s" % ", ".join(rules.social_monthly))
    social = sum(rules.social_monthly[k] * n for k, n in months.items())
    income = revenue - costs
    if form == "ryczalt":
        health = _health_ryczalt(revenue, rules)
        tax = max(0.0, rules.ryczalt_rate * (revenue - social) - 0.5 * health)
    elif form == "flat":
        health = max(rules.flat_health_rate * (income - social), rules.health_minimum_monthly * 12 * (1 if income > 0 else 0))
        deductible = min(health, rules.flat_health_deduction_limit)
        tax = max(0.0, rules.flat_rate * (income - social - deductible))
    elif form == "scale":
        health = max(rules.scale_health_rate * (income - social), rules.health_minimum_monthly * 12 * (1 if income > 0 else 0))
        base = max(0.0, income - social)
        tax = rules.scale_low * min(base, rules.scale_threshold) + rules.scale_high * max(0.0, base - rules.scale_threshold) - rules.scale_tax_free_reduction
        tax = max(0.0, tax)
    else:
        raise ValueError("form must be ryczalt, flat or scale")
    tax = round(tax)
    net = revenue - costs - social - health - tax
    return {"social": round(social, 2), "health": round(health, 2), "tax": float(tax), "net_year": round(net, 2), "net_month": round(net / 12, 2)}


def compare(revenue: float, costs: float, rules: Rules, months: Dict[str, int]) -> Dict[str, Dict[str, float]]:
    return {f: compute(revenue, costs, f, rules, months) for f in ("ryczalt", "flat", "scale")}


def best_form(revenue: float, costs: float, rules: Rules, months: Dict[str, int]) -> str:
    res = compare(revenue, costs, rules, months)
    return max(res, key=lambda f: res[f]["net_year"])


def required_revenue(target_net_month: float, costs_year: float, form: str, rules: Rules, months: Dict[str, int]) -> float:
    """The yearly revenue needed so that the monthly net equals the target, by bisection (net grows with revenue for every form)."""
    lo, hi = 0.0, 5_000_000.0
    if compute(hi, costs_year, form, rules, months)["net_month"] < target_net_month:
        raise ValueError("target is out of range")
    for _ in range(80):
        mid = (lo + hi) / 2
        if compute(mid, costs_year, form, rules, months)["net_month"] < target_net_month:
            lo = mid
        else:
            hi = mid
    return round(hi, 2)


def costs_break_even(revenue: float, rules: Rules, months: Dict[str, int], step: float = 500.0) -> float:
    """The yearly costs above which the flat 19% form beats ryczalt (the rule of thumb in numbers); None when it never does within the revenue."""
    c = 0.0
    while c < revenue:
        if compute(revenue, c, "flat", rules, months)["net_year"] > compute(revenue, c, "ryczalt", rules, months)["net_year"]:
            return c
        c += step
    return None
