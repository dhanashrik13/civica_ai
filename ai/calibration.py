import logging
from django.utils import timezone

logger = logging.getLogger(__name__)

class AICalibrationEngine:
    """
    Governance-Grade AI Confidence Calibration.
    Transforms LLM 'Self-Reported Confidence' into 'Calibrated Reliability'.
    Addresses WP-C3.
    """

    @staticmethod
    def analyze_ambiguity(input_text):
        """
        Detects specific ambiguity patterns in multilingual governance reports.
        """
        tags = []
        penalty = 1.0

        # 1. Transliteration Check (e.g., 'pani nahi' vs 'पाणी नाही')
        has_devanagari = any('\u0900' <= char <= '\u097F' for char in input_text)
        words = input_text.lower().split()
        marathish_keywords = ["pani", "kachra", "rasta", "light", "gaadi", "pothole", "ahe", "nahi"]
        is_transliterated = not has_devanagari and any(k in words for k in marathish_keywords)

        if is_transliterated:
            tags.append("Transliterated Marathi (Marathish)")
            penalty *= 0.85

        # 2. Context Depth (Word count)
        if len(words) < 5:
            tags.append("Low Context/Short Report")
            penalty *= 0.90

        # 3. Reference Ambiguity (Check for vague landmark references)
        vague_refs = ["mazya gharajaval", "near my house", "shalejaval", "near school"]
        if any(ref in input_text.lower() for ref in vague_refs):
            tags.append("Ambiguous Landmark Reference")
            penalty *= 0.95

        return {
            "tags": tags,
            "linguistic_penalty": penalty,
            "requires_human_clarification": penalty < 0.80 or len(tags) >= 2
        }

    @staticmethod
    def get_calibrated_confidence(raw_confidence, input_text, category):
        """
        De-biases self-reported scores using linguistic analysis and safety rules.
        """
        calibrated = float(raw_confidence)
        
        ambiguity = AICalibrationEngine.analyze_ambiguity(input_text)
        calibrated *= ambiguity['linguistic_penalty']

        # 2. High-Stakes Governance Guard
        # Categories like 'Security' or 'Health' require stricter certainty
        high_stakes = ["Security", "Health", "Emergency"]
        if category in high_stakes:
            calibrated *= 0.95 # Higher bar for auto-routing high-stakes issues

        return round(max(0.0, min(100.0, calibrated)), 2)

    @staticmethod
    def detect_trust_decay(issue_id, officer_override_count):
        """
        Conceptual: Detects if AI accuracy in a specific region is degrading.
        """
        if officer_override_count > 10:
            return True
        return False
