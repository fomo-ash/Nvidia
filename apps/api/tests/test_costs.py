from app.services.costs import summary
def test_cost_autopsy_reports_measured_and_estimated_values():
    result = summary()
    assert result["total_cost"] == 2450.0
    assert result["change_percent"] == 104.17
    assert result["estimated_savings"]["amount"] == 450.0
