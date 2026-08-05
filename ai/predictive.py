import logging
from django.utils import timezone
from django.db.models import Count, Avg, F
from issues.models import Issue
from accounts.models import Location, OfficerProfile, StaffingPolicy

logger = logging.getLogger(__name__)

class PredictiveGovernanceEngine:
    """
    Predictive Intelligence for Governance Operations.
    Forecasts overloads, SLA breaches, and staffing needs.
    """

    def predict_sla_breach_risk(self, issue):
        """
        Calculates probability of an issue breaching its SLA.
        Factors: Current officer workload, category history, district pressure.
        """
        if issue.status == Issue.Status.RESOLVED: return 0
        
        # 1. Base Risk (elapsed time)
        days_elapsed = (timezone.now() - issue.created_at).days
        sla_limit = issue.sla_days
        base_risk = (days_elapsed / sla_limit) * 50 if sla_limit > 0 else 100
        
        # 2. OfficerProfile Pressure
        if issue.assigned_to:
            workload = issue.assigned_to.assigned_issues.exclude(status=Issue.Status.RESOLVED).count()
            officer_factor = min(workload * 5, 30) # Max 30% add
        else:
            officer_factor = 40 # High risk if unassigned
            
        # 3. Seasonal/Category Trend
        # Demo: Check if this category had many breaches recently in this district
        breach_trend = Issue.objects.filter(
            district=issue.district,
            category=issue.category,
            status=Issue.Status.RESOLVED,
            resolved_at__gt=F('created_at') + timezone.timedelta(days=sla_limit)
        ).count()
        trend_factor = min(breach_trend * 2, 20)

        total_risk = min(int(base_risk + officer_factor + trend_factor), 100)
        
        return {
            "risk_score": total_risk,
            "probability": f"{total_risk}%",
            "drivers": {
                "time_decay": int(base_risk),
                "officer_workload": officer_factor,
                "historical_trend": trend_factor
            }
        }

    def forecast_district_overload(self, district_name):
        """
        Predicts if a district will face a 'Governance Storm' (high pressure).
        """
        dist = Location.objects.filter(type='district', name__iexact=district_name).first()
        if not dist: return None
        
        active_issues = Issue.objects.filter(district=dist.name).exclude(status=Issue.Status.RESOLVED).count()
        active_officers = OfficerProfile.objects.filter(district=dist.name, is_active=True).count()
        
        pressure_index = active_issues / active_officers if active_officers > 0 else active_issues
        
        # Prediction: Rising trend if 20% increase in new issues vs last week
        last_week = timezone.now() - timezone.timedelta(days=7)
        prev_week = last_week - timezone.timedelta(days=7)
        
        this_week_count = Issue.objects.filter(district=dist.name, created_at__gte=last_week).count()
        prev_week_count = Issue.objects.filter(district=dist.name, created_at__gte=prev_week, created_at__lt=last_week).count()
        
        is_surging = (this_week_count > prev_week_count * 1.2) if prev_week_count > 0 else False
        
        risk_level = "High" if pressure_index > 15 or is_surging else "Normal"
        
        return {
            "district": district_name,
            "pressure_index": round(pressure_index, 2),
            "is_surging": is_surging,
            "forecast": risk_level,
            "recommendation": "Redistribute L2 officers from neighboring districts" if risk_level == "High" else "Maintain current staffing"
        }

    def get_staffing_recommendations(self, district_name):
        """
        Suggests optimal staffing based on predicted workloads.
        """
        forecast = self.forecast_district_overload(district_name)
        if not forecast: return []
        
        recommendations = []
        if forecast['forecast'] == "High":
            # Find departments with highest gaps
            from accounts.services import analyze_district_coverage
            analysis = analyze_district_coverage(district_name=district_name)[0]
            
            if analysis['gap'] > 0:
                recommendations.append({
                    "action": "Urgent Expansion",
                    "reason": f"District overload predicted with {analysis['gap']} officer vacancy.",
                    "priority": "Critical"
                })
        
        return recommendations

def get_predictive_engine():
    return PredictiveGovernanceEngine()
