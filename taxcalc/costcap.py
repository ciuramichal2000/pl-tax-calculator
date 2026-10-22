"""A cost cap for automated work: every job has a revenue and may spend at most a share of it (and the whole fleet a monthly ceiling).
The tracker stops a job BEFORE it overspends, so a runaway worker cannot burn the budget."""
from dataclasses import dataclass, field
from typing import Dict, List


class BudgetExceeded(Exception):
    pass


@dataclass
class JobBudget:
    name: str
    monthly_revenue: float
    max_share: float = 0.25
    spent: float = 0.0
    log: List[str] = field(default_factory=list)

    @property
    def limit(self) -> float:
        return self.monthly_revenue * self.max_share

    @property
    def remaining(self) -> float:
        return max(0.0, self.limit - self.spent)


class CostCap:
    def __init__(self, monthly_ceiling: float, warn_at: float = 0.8):
        self.ceiling, self.warn_at = monthly_ceiling, warn_at
        self.jobs: Dict[str, JobBudget] = {}

    def add_job(self, name: str, monthly_revenue: float, max_share: float = 0.25) -> None:
        if monthly_revenue <= 0 or not 0 < max_share <= 1 or name in self.jobs:
            raise ValueError("a job needs a unique name, a positive revenue and a share between 0 and 1")
        self.jobs[name] = JobBudget(name, monthly_revenue, max_share)

    @property
    def total_spent(self) -> float:
        return sum(j.spent for j in self.jobs.values())

    def charge(self, name: str, cost: float, what: str = "") -> str:
        """Records a cost; raises BudgetExceeded WITHOUT recording it if it would break the job's limit or the fleet ceiling. Returns 'ok' or 'warning'."""
        if cost < 0:
            raise ValueError("a cost cannot be negative")
        j = self.jobs[name]
        if j.spent + cost > j.limit + 1e-9:
            raise BudgetExceeded("%s: %.2f would exceed its limit of %.2f (spent %.2f)" % (name, cost, j.limit, j.spent))
        if self.total_spent + cost > self.ceiling + 1e-9:
            raise BudgetExceeded("the monthly ceiling of %.2f would be exceeded (spent %.2f)" % (self.ceiling, self.total_spent))
        j.spent += cost
        j.log.append("%.2f %s" % (cost, what))
        return "warning" if j.spent >= self.warn_at * j.limit else "ok"

    def report(self) -> List[Dict[str, object]]:
        return [{"job": j.name, "revenue": j.monthly_revenue, "spent": round(j.spent, 2), "limit": round(j.limit, 2), "profit_before_tax": round(j.monthly_revenue - j.spent, 2),
                 "state": "over" if j.spent > j.limit else "warning" if j.spent >= self.warn_at * j.limit else "ok"} for j in self.jobs.values()]
