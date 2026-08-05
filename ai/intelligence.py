import numpy as np
import logging
from .assistant import CivicAIAssistant
from django.utils import timezone
from django.db.models import Count, Q

logger = logging.getLogger(__name__)

class CivicIntelligenceEngine:
    """
    Enterprise Intelligence Engine for Maharashtra Governance.
    Handles semantic clustering, fraud detection, and anomaly alerts.
    """
    
    def __init__(self):
        self.ai = CivicAIAssistant()

    def find_semantic_duplicates(self, issue, threshold=0.85):
        """
        Detects duplicates using pre-computed vector embeddings.
        Eliminates redundant API calls and scales linearly (Embedding Scalability Optimization).
        """
        from issues.models import Issue, IssueEmbedding
        
        # 1. Fetch Source Vector
        source_vector_obj = IssueEmbedding.objects.filter(issue=issue).first()
        if not source_vector_obj:
            # Fallback if enrichment task hasn't completed yet
            text_to_embed = f"{issue.title} {issue.description}"
            source_vector = self.ai.get_embedding(text_to_embed)
        else:
            source_vector = source_vector_obj.vector

        if not source_vector:
            return []

        # 2. Fetch Candidate Vectors from DB (No API calls!)
        # Filtered by location for massive scale reduction
        candidates = IssueEmbedding.objects.filter(
            issue__district=issue.district,
            issue__created_at__gte=timezone.now() - timezone.timedelta(days=15)
        ).exclude(issue=issue).select_related('issue')[:100]

        duplicates = []
        for cand in candidates:
            similarity = self._cosine_similarity(source_vector, cand.vector)
            if similarity >= threshold:
                duplicates.append({
                    "issue_id": cand.issue.id,
                    "similarity": round(similarity * 100, 2),
                    "reason": "Semantic similarity detected (Local Vector Match)"
                })

        return sorted(duplicates, key=lambda x: x['similarity'], reverse=True)

    def detect_governance_fraud(self, user, issue):
        """
        Advanced Fraud Intelligence.
        Detects bot patterns, coordination, and reporter manipulation.
        """
        from issues.models import Issue
        
        risk_flags = []
        confidence = 0

        # 1. Coordinated Reporting Spike
        # If 20+ issues with same category in same village in 30 mins
        one_hour_ago = timezone.now() - timezone.timedelta(minutes=60)
        local_spike = Issue.objects.filter(
            village=issue.village,
            category=issue.category,
            created_at__gte=one_hour_ago
        ).count()
        
        if local_spike > 20:
            risk_flags.append("Localized coordinated spike detected")
            confidence += 40

        # 2. Bot-like Activity (Temporal regularity & Jitter Analysis)
        user_recent = Issue.objects.filter(reported_by=user, created_at__gte=one_hour_ago).order_by('created_at')
        if user_recent.count() > 5:
            intervals = []
            for i in range(1, user_recent.count()):
                diff = (user_recent[i].created_at - user_recent[i-1].created_at).total_seconds()
                intervals.append(diff)
            
            # HARDENED: Check for jittered patterns (Low variance in intervals)
            if len(intervals) > 3:
                std_dev = np.std(intervals)
                if std_dev < 5.0: # Even with jitter, bots often have a tight range
                    risk_flags.append(f"Suspicious temporal regularity (StdDev: {std_dev:.2f}s)")
                    confidence += 50

        # 3. Content Entropy & Duplication
        if user_recent.count() > 3:
            titles = [i.title.lower() for i in user_recent]
            unique_titles = set(titles)
            dupe_ratio = 1 - (len(unique_titles) / len(titles))
            if dupe_ratio > 0.5:
                risk_flags.append(f"High content duplication detected ({dupe_ratio*100:.1f}%)")
                confidence += 40

        return {
            "is_suspicious": confidence >= 50,
            "fraud_score": confidence,
            "flags": risk_flags,
            "action": "Human review required" if confidence >= 50 else "Proceed"
        }

    def _cosine_similarity(self, v1, v2):
        return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))

def get_intel_engine():
    return CivicIntelligenceEngine()
