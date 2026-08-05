import logging
from .assistant import CivicAIAssistant

logger = logging.getLogger(__name__)

class CitizenCopilot:
    """
    Empathetic, Conversational Civic Assistant.
    Provides guidance, clarifies issues, and explains governance decisions.
    """
    
    def __init__(self):
        self.ai = CivicAIAssistant()

    def handle_interaction(self, user, message, session_history=None):
        """
        Processes a citizen's conversational input.
        If context is missing (e.g., location), asks clarifying questions.
        """
        context = {
            "user_name": user.full_name,
            "role": "citizen",
            "history": session_history[-5:] if session_history else []
        }
        
        analysis = self.ai.process_input(message, user_role="citizen", context=context)
        
        # 1. Check for Missing Evidence/Info
        response_text = analysis['response']
        
        if analysis['intent'] == "issue reporting":
            # If AI confidence is low on entities, add follow-ups
            entities = analysis.get('entities', {})
            if not entities.get('infrastructure') or not entities.get('location_hints'):
                response_text += "\n\n(Follow-up: Could you please specify the exact landmark or the type of infrastructure affected? This helps our team reach the spot faster.)"
        
        return {
            "text": response_text,
            "analysis": analysis,
            "xai": analysis.get('analysis', {}).get('explainability', "Classification based on reported severity and public impact.")
        }

    def explain_issue_status(self, issue):
        """
        Provides a citizen-friendly explanation of why an issue is in its current state.
        Uses Predictive AI to manage expectations.
        """
        from .predictive import get_predictive_engine
        predictive = get_predictive_engine()
        risk = predictive.predict_sla_breach_risk(issue)
        
        explanation = f"Hello {issue.reported_by.full_name}, your report regarding '{issue.title}' is currently '{issue.get_status_display()}'. "
        
        if issue.status == "pending":
            explanation += "We are currently identifying the best available officer for this task."
        elif issue.status == "assigned":
            explanation += f"It has been assigned to {issue.assigned_to.user.full_name} from the {issue.department.name}."
            if risk['risk_score'] > 70:
                explanation += " Due to a high volume of reports in your area, there might be a slight delay, but our team is prioritizing it."
        
        return explanation

def get_citizen_copilot():
    return CitizenCopilot()
