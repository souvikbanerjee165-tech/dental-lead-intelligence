"""
Interactive Dental ROI Calculator & Patient Leakage Modeler (Agency Machine Pillar 3).
Calculates lost revenue economics based on practice appointments, treatment values, and missed inquiries.
"""

from typing import Dict, Any, Optional

class ROICalculator:
    """Calculates practice-specific unit economics, uncaptured revenue, and net ROI."""

    @classmethod
    def calculate(
        cls,
        monthly_appointments: int = 180,
        average_treatment_value: float = 1250.0,
        estimated_missed_calls_monthly: int = 15,
        after_hours_inquiry_ratio: float = 0.38,
        conversion_recovery_rate: float = 0.32,
        monthly_software_cost: float = 399.0,
        setup_fee: float = 1500.0
    ) -> Dict[str, Any]:
        """
        Computes empirical annual revenue loss and projected recovery ROI.
        """
        monthly_appts = max(10, monthly_appointments)
        avg_val = max(100.0, float(average_treatment_value))
        missed_calls = max(1, estimated_missed_calls_monthly)

        # 1. Uncaptured After-Hours Patients
        # Total inbound interest including unplaced calls/abandoned web visitors
        estimated_total_missed_inquiries = int(missed_calls + (monthly_appts * after_hours_inquiry_ratio * 0.25))
        
        # Monthly & Annual Lost Revenue
        monthly_lost_revenue = round(estimated_total_missed_inquiries * avg_val * 0.50, 2)
        annual_lost_revenue = round(monthly_lost_revenue * 12, 2)

        # 2. Recaptured Patients with 24/7 Conversational AI
        patients_recaptured_monthly = max(2, int(estimated_total_missed_inquiries * conversion_recovery_rate))
        recaptured_monthly_revenue = round(patients_recaptured_monthly * avg_val, 2)
        recaptured_annual_revenue = round(recaptured_monthly_revenue * 12, 2)

        # 3. Net ROI Multiple
        annual_software_investment = (monthly_software_cost * 12) + setup_fee
        net_annual_profit = max(0.0, recaptured_annual_revenue - annual_software_investment)
        roi_multiple = round(recaptured_annual_revenue / max(1.0, annual_software_investment), 1)

        # Summary Pitch Headline
        summary_headline = (
            f"Estimated Uncaptured Production: ${annual_lost_revenue:,.0f}/year. "
            f"Recovering just {patients_recaptured_monthly} extra patients monthly generates "
            f"+${recaptured_annual_revenue:,.0f}/year in chair production ({roi_multiple}× annual ROI)."
        )

        return {
            "inputs": {
                "monthly_appointments": monthly_appts,
                "average_treatment_value": avg_val,
                "estimated_missed_calls_monthly": missed_calls,
                "setup_fee": setup_fee,
                "monthly_software_cost": monthly_software_cost
            },
            "unrecovered_losses": {
                "estimated_missed_inquiries_monthly": estimated_total_missed_inquiries,
                "monthly_lost_revenue": monthly_lost_revenue,
                "annual_lost_revenue": annual_lost_revenue
            },
            "projected_recapture": {
                "patients_recaptured_monthly": patients_recaptured_monthly,
                "recaptured_monthly_revenue": recaptured_monthly_revenue,
                "recaptured_annual_revenue": recaptured_annual_revenue
            },
            "economic_roi": {
                "annual_software_investment": annual_software_investment,
                "net_annual_profit": net_annual_profit,
                "roi_multiple": f"{roi_multiple}x"
            },
            "summary_headline": summary_headline
        }
