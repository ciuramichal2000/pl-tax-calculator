# pl-tax-calculator

A planning aid for a Polish sole proprietorship: it compares **ryczalt (flat-rate), the flat 19% tax and the progressive scale**, including social and health contributions, tells you which form leaves more in your pocket, and answers "how much must I invoice to keep N zloty per month?". A second module, `costcap`, limits what automated work may spend: each job gets a share of its own revenue and the whole fleet a monthly ceiling, and a charge that would break a limit is refused before it is recorded.

**Not tax advice, and not current by itself.** Rates, thresholds and contribution amounts change by law and by year. They live in one `Rules` object, and the defaults are **assumed illustration values**; pass the real figures for the year (from ZUS, the tax office or your accountant). The logic is tested with explicit rules that can be checked by hand, independent of those defaults.

```python
from taxcalc import Rules, compare, required_revenue
rules = Rules()                                           # replace with the real figures for the year
months = {"start": 6, "preferential": 6, "full": 0}       # contribution regime per month
print(compare(120000, 10000, rules, months))
print(required_revenue(5100, 6000, "ryczalt", rules, months))   # yearly revenue for 5,100 net per month
```

`python -m pytest` runs the tests. Standard library only. Built with AI coding assistance.
