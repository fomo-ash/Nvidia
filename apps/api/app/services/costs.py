from decimal import Decimal

SAMPLE_COSTS = [
    {"period":"2026-09", "service":"Compute", "resource":"api-workers", "region":"ap-south-1", "cost":1200.00},
    {"period":"2026-10", "service":"Compute", "resource":"api-workers", "region":"ap-south-1", "cost":2100.00},
    {"period":"2026-10", "service":"Storage", "resource":"audit-logs", "region":"ap-south-1", "cost":350.00},
]
def summary():
    latest = [x for x in SAMPLE_COSTS if x["period"] == "2026-10"]
    previous = [x for x in SAMPLE_COSTS if x["period"] == "2026-09"]
    current = sum(Decimal(str(x["cost"])) for x in latest)
    prior = sum(Decimal(str(x["cost"])) for x in previous)
    return {"current_period": "2026-10", "total_cost": float(current), "previous_total": float(prior), "change": float(current-prior), "change_percent": round(float((current-prior)/prior*100), 2) if prior else None, "drivers": latest, "estimated_savings": {"amount": 450.0, "assumption": "Reduce over-provisioned api-workers capacity by 25%."}}
