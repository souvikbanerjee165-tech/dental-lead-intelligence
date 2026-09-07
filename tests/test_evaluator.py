import pytest
from evaluator import BenchmarkEvaluator, MetricScore

def test_metric_score_calculations():
    m = MetricScore(name="Test Metric", tp=10, tn=8, fp=2, fn=1)
    assert m.total == 21
    # Precision = 10 / (10 + 2) = 10 / 12 = 0.833
    assert m.precision == 0.833
    # Recall = 10 / (10 + 1) = 10 / 11 = 0.909
    assert m.recall == 0.909
    # Accuracy = (10 + 8) / 21 = 18 / 21 = 0.857
    assert m.accuracy == 0.857
    assert m.f1 > 0.8

def test_benchmark_evaluator_against_ground_truth():
    evaluator = BenchmarkEvaluator()
    result = evaluator.run_benchmark()

    assert result.evaluated_clinics_count >= 5
    assert result.overall_accuracy_pct >= 95.0
    assert len(result.failures) == 0

    # Ensure core detectors are evaluated
    assert "Online Booking" in result.metrics
    assert "AI Chatbot" in result.metrics
    assert "CMS Detection" in result.metrics
    assert "GA4 Analytics" in result.metrics
    assert "Ad Pixels" in result.metrics

    assert result.metrics["Online Booking"].precision >= 0.95
    assert result.metrics["AI Chatbot"].precision >= 0.95
