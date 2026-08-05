import logging
from django.db.models import Avg, F
from django.utils import timezone
from issues.models import Issue, CategoryIntelligence, IntelligenceLog

logger = logging.getLogger(__name__)

class CivicLearningEngine:
    """
    Autonomous Continuous Learning Loops for Civic AI.
    Learns from operational outcomes to refine predictions and recommendations.
    """

    def sync_intelligence_from_outcomes(self, category_name):
        """
        Analyzes recent resolutions for a category and updates its difficulty model.
        Uses learning stability to prevent erratic model shifts.
        """
        try:
            intel, _ = CategoryIntelligence.objects.get_or_create(category=category_name)
            
            # 1. Fetch recent resolutions (Last 100 or 30 days)
            resolved_issues = Issue.objects.filter(
                category=category_name,
                status=Issue.Status.RESOLVED,
                resolved_at__isnull=False
            ).order_by('-resolved_at')[:100]
            
            if not resolved_issues.exists():
                return False

            # 2. Calculate New Metrics
            # avg_time in hours
            total_hours = sum([
                (i.resolved_at - i.created_at).total_seconds() / 3600 
                for i in resolved_issues
            ])
            actual_avg = total_hours / resolved_issues.count()
            
            # 3. Dynamic Difficulty Score
            # If actual avg > expected avg, difficulty increases
            expected_avg = intel.avg_resolution_hours
            new_difficulty = intel.difficulty_score * (actual_avg / expected_avg) if expected_avg > 0 else 1.0
            
            # Clamp difficulty (0.5 to 3.0)
            new_difficulty = max(0.5, min(3.0, new_difficulty))

            # 4. Apply Learning Stability (Smoothing)
            alpha = intel.learning_stability
            final_avg = (alpha * intel.avg_resolution_hours) + ((1 - alpha) * actual_avg)
            final_difficulty = (alpha * intel.difficulty_score) + ((1 - alpha) * new_difficulty)

            # 5. Log & Update
            if abs(final_avg - intel.avg_resolution_hours) > 1.0: # Only log significant shifts
                IntelligenceLog.objects.create(
                    category=category_name,
                    change_type='avg_resolution_hours',
                    old_value=intel.avg_resolution_hours,
                    new_value=final_avg,
                    reason=f"Auto-learned from {resolved_issues.count()} recent resolutions."
                )

            intel.avg_resolution_hours = final_avg
            intel.difficulty_score = final_difficulty
            intel.total_resolved = Issue.objects.filter(category=category_name, status=Issue.Status.RESOLVED).count()
            intel.save()
            
            logger.info(f"[CIVIC LEARNING] Evolved model for {category_name}: Diff={final_difficulty:.2f}")
            return True

        except Exception as e:
            logger.error(f"[CIVIC LEARNING] Evolution Failure for {category_name}: {str(e)}")
            return False

    def learn_from_appeals(self):
        """
        Learns from Escalation Appeal reversals.
        If appeals for a department are frequently approved, reliability scores should adjust.
        """
        # (Conceptual implementation for enterprise maturity)
        pass

def get_learning_engine():
    return CivicLearningEngine()
