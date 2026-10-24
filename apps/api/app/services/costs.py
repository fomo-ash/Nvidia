"""Deterministic sample billing arithmetic. Estimates are explicit and row-derived."""

from decimal import Decimal, ROUND_HALF_UP

SAMPLE_COSTS = [
    {
        "period": "2026-09",
        "service": "Compute",
        "resource": "api-workers",
        "region": "ap-south-1",
        "cost": 1200.00,
    },
    {
        "period": "2026-10",
        "service": "Compute",
        "resource": "api-workers",
        "region": "ap-south-1",
        "cost": 2100.00,
    },
    {
        "period": "2026-10",
        "service": "Storage",
        "resource": "audit-logs",
        "region": "ap-south-1",
        "cost": 350.00,
    },
]


def money(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def summary(rows=None, *, current_period="2026-10", previous_period="2026-09"):
    rows = SAMPLE_COSTS if rows is None else rows
    if previous_period >= current_period:
        raise ValueError("Previous period must precede current period")
    latest = [row for row in rows if row["period"] == current_period]
    previous = [row for row in rows if row["period"] == previous_period]
    if not latest or not previous:
        raise ValueError("Both billing periods require source records")
    values = [Decimal(str(row["cost"])) for row in latest + previous]
    if any(not value.is_finite() or value < 0 for value in values):
        raise ValueError("Sample billing costs must be finite and nonnegative")
    current = sum((Decimal(str(row["cost"])) for row in latest), Decimal(0))
    prior = sum((Decimal(str(row["cost"])) for row in previous), Decimal(0))
    eligible = sum(
        (
            Decimal(str(row["cost"]))
            for row in latest
            if row["service"] == "Compute" and row["resource"] == "api-workers"
        ),
        Decimal(0),
    )
    groups = {}
    for row in previous + latest:
        key = (
            row.get("service", "Unknown"),
            row.get("resource", "Unknown"),
            row.get("region", "Unknown"),
        )
        group = groups.setdefault(key, {current_period: Decimal(0), previous_period: Decimal(0)})
        group[row["period"]] += Decimal(str(row["cost"]))
    drivers = [
        {
            "period": current_period,
            "service": service,
            "resource": resource,
            "region": region,
            "cost": money(totals[current_period]),
            "previous_cost": money(totals[previous_period]),
            "change": money(totals[current_period] - totals[previous_period]),
        }
        for (service, resource, region), totals in groups.items()
    ]
    drivers.sort(
        key=lambda row: (-abs(row["change"]), row["service"], row["resource"], row["region"])
    )
    return {
        "mode": "synthetic",
        "currency": "USD",
        "current_period": current_period,
        "previous_period": previous_period,
        "total_cost": money(current),
        "previous_total": money(prior),
        "change": money(current - prior),
        "change_percent": money((current - prior) / prior * 100) if prior else None,
        "drivers": drivers,
        "estimated_savings": {
            "amount": money(eligible * Decimal("0.25")),
            "assumption": "Assume api-workers compute capacity and its cost can both fall by 25%, with unchanged rates and workload health. Not measured savings.",
            "formula": f"{money(eligible):.2f} USD eligible compute cost × 0.25",
        },
    }
