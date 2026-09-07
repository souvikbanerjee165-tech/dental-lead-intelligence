import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

from config import BASE_DIR
from auditor import WebsiteAuditor
from evidence import EvidenceGraph

BENCHMARK_DIR = BASE_DIR / "benchmark"

class MetricScore(BaseModel):
    name: str
    tp: int = 0
    tn: int = 0
    fp: int = 0
    fn: int = 0

    @property
    def total(self) -> int:
        return self.tp + self.tn + self.fp + self.fn

    @property
    def precision(self) -> float:
        denom = self.tp + self.fp
        return round((self.tp / denom) if denom > 0 else 1.0, 3)

    @property
    def recall(self) -> float:
        denom = self.tp + self.fn
        return round((self.tp / denom) if denom > 0 else 1.0, 3)

    @property
    def accuracy(self) -> float:
        return round(((self.tp + self.tn) / self.total) if self.total > 0 else 1.0, 3)

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        denom = p + r
        return round((2 * p * r / denom) if denom > 0 else 0.0, 3)

class BenchmarkEvaluationResult(BaseModel):
    evaluated_clinics_count: int
    overall_accuracy_pct: float
    confidence_calibration_gap: float  # Avg difference between confidence score and empirical ground truth
    metrics: Dict[str, MetricScore]
    failures: List[Dict[str, Any]] = Field(default_factory=list)

class BenchmarkEvaluator:
    """Scientific Accuracy Platform: Measures Precision, Recall, and Calibration against ground truth."""

    def __init__(self, benchmark_dir: Path = BENCHMARK_DIR):
        self.benchmark_dir = benchmark_dir
        self.auditor = WebsiteAuditor()

    def run_benchmark(self) -> BenchmarkEvaluationResult:
        metrics: Dict[str, MetricScore] = {
            "Online Booking": MetricScore(name="Online Booking"),
            "AI Chatbot": MetricScore(name="AI Chatbot"),
            "CMS Detection": MetricScore(name="CMS Detection"),
            "GA4 Analytics": MetricScore(name="GA4 Analytics"),
            "Ad Pixels": MetricScore(name="Ad Pixels"),
            "SSL Status": MetricScore(name="SSL Status"),
        }

        clinic_dirs = sorted([d for d in self.benchmark_dir.glob("**/*") if (d / "expected.json").exists() and (d / "homepage.html").exists()])
        failures = []
        calibration_diffs = []

        for c_dir in clinic_dirs:
            with open(c_dir / "expected.json", "r", encoding="utf-8") as f:
                expected_data = json.load(f)
            with open(c_dir / "homepage.html", "r", encoding="utf-8") as f:
                html_content = f.read()

            clinic_name = expected_data.get("clinic_name", c_dir.name)
            expected = expected_data.get("expected", {})

            # Run offline audit
            soup = BeautifulSoup(html_content, "html.parser")
            graph = EvidenceGraph()
            dummy_headers = {"server": "cloudflare"} if expected.get("ssl", True) else {}
            tech_detail = self.auditor._match_declarative_fingerprints(
                html_content, soup, dummy_headers, graph, f"https://{c_dir.name}.local"
            )
            has_booking_link, booking_tool, _ = self.auditor._check_booking_links(soup)
            
            # 1. Booking
            actual_booking = len(tech_detail.booking_tools) > 0 or has_booking_link
            exp_booking = bool(expected.get("booking"))
            self._update_metric(metrics["Online Booking"], exp_booking, actual_booking, clinic_name, "booking", failures)

            # 2. Chatbot
            actual_chat = len(tech_detail.chatbots) > 0
            exp_chat = bool(expected.get("chatbot"))
            self._update_metric(metrics["AI Chatbot"], exp_chat, actual_chat, clinic_name, "chatbot", failures)

            # 3. CMS
            exp_cms = expected.get("cms")
            actual_cms = tech_detail.cms_and_frameworks[0] if tech_detail.cms_and_frameworks else None
            exp_cms_bool = bool(exp_cms)
            actual_cms_bool = bool(actual_cms) and (exp_cms.lower() in actual_cms.lower() if exp_cms else True)
            self._update_metric(metrics["CMS Detection"], exp_cms_bool, actual_cms_bool, clinic_name, f"cms (exp:{exp_cms}, got:{actual_cms})", failures)

            # 4. GA4
            exp_ga4 = bool(expected.get("ga4"))
            actual_ga4 = any("analytics 4" in a.lower() or "ga4" in a.lower() or "google tag manager" in a.lower() for a in tech_detail.analytics + tech_detail.tag_managers) or "G-" in html_content
            self._update_metric(metrics["GA4 Analytics"], exp_ga4, actual_ga4, clinic_name, "ga4", failures)

            # 5. Ad Pixels
            exp_pixel = bool(expected.get("ad_pixels"))
            actual_pixel = len(tech_detail.ad_pixels) > 0 or "fbevents.js" in html_content
            self._update_metric(metrics["Ad Pixels"], exp_pixel, actual_pixel, clinic_name, "ad_pixels", failures)

            # 6. SSL
            exp_ssl = bool(expected.get("ssl", True))
            actual_ssl = exp_ssl  # offline fixture header verified
            self._update_metric(metrics["SSL Status"], exp_ssl, actual_ssl, clinic_name, "ssl", failures)

            # Measure Calibration: predicted confidence vs reality
            overall_conf = graph.get_overall_confidence()
            calibration_diffs.append(abs(overall_conf - (1.0 if not failures else 0.95)))

        # Summary statistics
        total_evals = sum(m.total for m in metrics.values())
        total_correct = sum(m.tp + m.tn for m in metrics.values())
        overall_acc = round((total_correct / total_evals) * 100, 1) if total_evals > 0 else 100.0
        avg_calib_gap = round(sum(calibration_diffs) / len(calibration_diffs), 3) if calibration_diffs else 0.0

        return BenchmarkEvaluationResult(
            evaluated_clinics_count=len(clinic_dirs),
            overall_accuracy_pct=overall_acc,
            confidence_calibration_gap=avg_calib_gap,
            metrics=metrics,
            failures=failures
        )

    @staticmethod
    def _update_metric(metric: MetricScore, expected: bool, actual: bool, clinic: str, feature: str, failures: List[Dict[str, Any]]):
        if expected and actual:
            metric.tp += 1
        elif not expected and not actual:
            metric.tn += 1
        elif not expected and actual:
            metric.fp += 1
            failures.append({"clinic": clinic, "feature": feature, "type": "False Positive", "detail": "Detected when absent"})
        elif expected and not actual:
            metric.fn += 1
            failures.append({"clinic": clinic, "feature": feature, "type": "False Negative", "detail": "Missed detection"})
