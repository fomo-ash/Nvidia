from app.services.costs import summary
import pytest


def test_cost_autopsy_reports_measured_and_estimated_values():
    result = summary()
    assert result["total_cost"] == 2450.0
    assert result["change_percent"] == 104.17
    assert result["estimated_savings"]["amount"] == 525.0
    assert result["change"] == 1250
    assert result["mode"] == "synthetic"
    assert "2100.00" in result["estimated_savings"]["formula"]
    assert result["drivers"][0]["resource"] == "api-workers"
    assert result["drivers"][0]["change"] == 900
    assert sum(row["change"] for row in result["drivers"]) == result["change"]


def test_zero_baseline_has_no_percentage():
    result = summary(
        [
            {"period": "2026-09", "cost": 0},
            {"period": "2026-10", "cost": "0.10", "service": "Storage", "resource": "logs"},
            {"period": "2026-10", "cost": "0.20", "service": "Storage", "resource": "logs"},
        ]
    )
    assert result["total_cost"] == 0.3
    assert result["change_percent"] is None
    assert result["estimated_savings"]["amount"] == 0


@pytest.mark.parametrize("cost", [-1, "NaN", "Infinity"])
def test_invalid_costs_are_rejected(cost):
    with pytest.raises(ValueError):
        summary([{"period": "2026-09", "cost": 1}, {"period": "2026-10", "cost": cost}])


def test_missing_or_reversed_periods_are_not_treated_as_zero_spend():
    with pytest.raises(ValueError):
        summary([])
    with pytest.raises(ValueError):
        summary(current_period="2026-09", previous_period="2026-10")
