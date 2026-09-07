from typing import List, Dict, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field

class DetectorMetadata(BaseModel):
    """Institutionalized quality, ownership, and versioning for empirical detectors."""
    detector_id: str
    name: str
    version: str
    category: str
    owner: str = "Core Engineering"
    benchmark_sites: int = 5
    benchmark_accuracy_pct: float = 100.0
    last_updated: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    changelog: List[str] = Field(default_factory=list)

class DetectorRegistry:
    """Central registry tracking detector versions, maintainers, and ground-truth benchmark coverage."""

    _DETECTORS: Dict[str, DetectorMetadata] = {
        "detector.booking": DetectorMetadata(
            detector_id="detector.booking",
            name="Online Appointment Scheduling Detector",
            version="1.4.0",
            category="Patient Experience & Accessibility",
            owner="Core Engineering",
            benchmark_sites=5,
            benchmark_accuracy_pct=100.0,
            changelog=[
                "v1.4.0: Added LocalMed, NexHealth widget & inline anchor detection",
                "v1.3.0: Added Calendly, Acuity, Zocdoc external network signatures",
                "v1.0.0: Initial regex pattern detector"
            ]
        ),
        "detector.chatbot": DetectorMetadata(
            detector_id="detector.chatbot",
            name="24/7 Conversational AI Receptionist Detector",
            version="1.3.2",
            category="Automation & AI Intake",
            owner="Core Engineering",
            benchmark_sites=5,
            benchmark_accuracy_pct=100.0,
            changelog=[
                "v1.3.2: Multi-detector script SDK agreement boost",
                "v1.2.0: Added Weave, Podium, Drift, Intercom, LiveChat fingerprints",
                "v1.0.0: Initial chatbot detector"
            ]
        ),
        "detector.cms": DetectorMetadata(
            detector_id="detector.cms",
            name="CMS & Web Architecture Fingerprinter",
            version="2.1.0",
            category="Website Architecture",
            owner="Core Engineering",
            benchmark_sites=5,
            benchmark_accuracy_pct=100.0,
            changelog=[
                "v2.1.0: Added Next.js __NEXT_DATA__ and Nuxt SSR detection",
                "v2.0.0: Declarative YAML migration (WordPress, Wix, Squarespace, Shopify)"
            ]
        ),
        "detector.analytics": DetectorMetadata(
            detector_id="detector.analytics",
            name="GA4 & Tag Management Detector",
            version="1.2.0",
            category="Analytics & Infrastructure",
            owner="Core Engineering",
            benchmark_sites=5,
            benchmark_accuracy_pct=100.0,
            changelog=[
                "v1.2.0: Google Analytics 4 G- measurement ID and GTM container parser",
                "v1.0.0: UA/GA legacy tag matching"
            ]
        ),
        "detector.pixels": DetectorMetadata(
            detector_id="detector.pixels",
            name="Advertising Retargeting Pixels Detector",
            version="1.1.0",
            category="Paid Acquisition",
            owner="Core Engineering",
            benchmark_sites=5,
            benchmark_accuracy_pct=100.0,
            changelog=[
                "v1.1.0: Meta Pixel fbevents.js, Google Ads conversion tag",
                "v1.0.0: Initial pixel scanner"
            ]
        ),
        "detector.crm": DetectorMetadata(
            detector_id="detector.crm",
            name="CRM & Lead Pipeline Detector",
            version="1.2.0",
            category="Automation & Marketing",
            owner="Core Engineering",
            benchmark_sites=5,
            benchmark_accuracy_pct=100.0,
            changelog=[
                "v1.2.0: GoHighLevel (msgsndr.com / leadconnector), HubSpot, ActiveCampaign",
                "v1.0.0: Basic CRM tag scanner"
            ]
        )
    }

    @classmethod
    def get_detector(cls, detector_id: str) -> Optional[DetectorMetadata]:
        return cls._DETECTORS.get(detector_id)

    @classmethod
    def list_detectors(cls) -> List[DetectorMetadata]:
        return list(cls._DETECTORS.values())
