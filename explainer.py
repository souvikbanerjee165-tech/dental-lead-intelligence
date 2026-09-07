import os
from typing import List, Optional
from config import GEMINI_API_KEY
from models import ScoredLead

class ScoreExplainer:
    """Generates transparent, dentist-friendly 'Why [Score]?' rationale bullet points using Gemini or deterministic rules."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or GEMINI_API_KEY
        self.client = None
        if self.api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
            except Exception:
                self.client = None

    def explain_score(self, lead: ScoredLead) -> List[str]:
        """Returns 3-4 clear bullet points explaining why the clinic received its opportunity score."""
        # Try Gemini Generative Explanation if configured
        if self.client:
            try:
                raw = lead.raw_lead
                audit = lead.audit
                score = lead.opportunity_score
                min_rev = lead.estimated_missed_revenue_monthly_min
                max_rev = lead.estimated_missed_revenue_monthly_max

                prompt = (
                    f"You are an executive dental practice growth consultant.\n"
                    f"A dental clinic was audited for patient capture & after-hours intake readiness.\n"
                    f"Clinic: {raw.name}\n"
                    f"Opportunity Score: {score}/100\n"
                    f"Google Rating: {raw.rating or 4.9} stars ({raw.review_count or 0} reviews)\n"
                    f"Online Booking: {'Present' if audit.has_online_booking else 'MISSING'}\n"
                    f"WhatsApp / 24/7 AI Chat: {'Present' if (audit.has_ai_chatbot or audit.has_whatsapp) else 'MISSING'}\n"
                    f"Estimated After-Hours Leakage: ${min_rev:,.0f}–${max_rev:,.0f}/month\n\n"
                    f"Write exactly 3 or 4 concise bullet points explaining 'Why {score}/100?' to the practice owner.\n"
                    f"Focus on practical consequences: after-hours patient leakage, daytime phone tag, lost chair production, and missed emergency cases.\n"
                    f"Format rules:\n"
                    f"- Each bullet must start with '• '\n"
                    f"- Under 15 words per bullet\n"
                    f"- No intro, outro, or conversational filler."
                )

                response = self.client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt
                )
                if response and response.text:
                    lines = [l.strip() for l in response.text.split("\n") if l.strip().startswith("•") or l.strip().startswith("-") or l.strip().startswith("*")]
                    cleaned = [f"• {l.lstrip('•-* ').strip()}" for l in lines if l]
                    if len(cleaned) >= 2:
                        return cleaned[:4]
            except Exception:
                # Fallback on any error or timeout
                pass

        # Robust Deterministic Fallback Engine
        return self.fallback_reasons(lead)

    @staticmethod
    def fallback_reasons(lead: ScoredLead) -> List[str]:
        raw = lead.raw_lead
        audit = lead.audit
        score = lead.opportunity_score
        bullets = []

        if not audit.has_online_booking:
            bullets.append("• No after-hours booking detected (forces prospective patients into daytime phone tag)")
        
        if not audit.has_ai_chatbot and not audit.has_whatsapp:
            bullets.append("• Zero 24/7 AI chat or WhatsApp automation active for after-hours patient triage")

        if not audit.has_clickable_phone:
            bullets.append("• Mobile contact button is hidden or not directly dialable on mobile viewport")

        if raw.review_count and raw.review_count >= 40:
            bullets.append(f"• High search volume ({raw.review_count} reviews) means ~42% of evening patient inquiries are lost")
        elif not audit.has_faq_section:
            bullets.append("• Missing insurance & pricing FAQ causes emergency patients to bounce to competitors")

        if not audit.has_ssl:
            bullets.append("• Insecure website connection (HTTP) flags security warnings to patients")

        if len(bullets) < 3:
            bullets.append("• Inability to automatically text back missed callers when front desk is busy")

        return bullets[:4]
