import os
import json
import time
import hashlib
import uuid
import logging
from django.conf import settings
from django.db import transaction, OperationalError
from django.core.signing import Signer, BadSignature
from django.core.cache import cache
from openai import OpenAI
from issues.models import Issue
from accounts.models import OfficerProfile
from django.db.models import Count
from django.utils import timezone
from .models import AIChat, AIActionLog
# Import shared config for consistency
from ai.config import SYSTEM_CATEGORIES, SYSTEM_PRIORITIES, DEPARTMENT_MAPPING

# Setup Logger
logger = logging.getLogger(__name__)
signer = Signer()

# Configuration
ROLE_PERMISSIONS = {
    "super_admin": ["assign_officer", "mark_resolved"],
    "dept_admin": ["assign_officer", "mark_resolved"],
    "officer": ["mark_resolved"],
}

ALLOWED_ACTIONS_SCHEMA = {
    "assign_officer": ["issue_id", "officer_id"],
    "mark_resolved": ["issue_id"],
}

def send_to_monitoring_service(event_type, details):
    log_msg = f"[MONITORING] {event_type} | {json.dumps(details)}"
    logger.error(log_msg) if "fail" in event_type.lower() else logger.info(log_msg)

def get_openai_client():
    api_key = getattr(settings, "OPENAI_API_KEY", "") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY is not configured.")
        return None
    return OpenAI(api_key=api_key)

def ai_fallback_reply(user_message, reason="unavailable"):
    """Rule-based fallback aligned with system stats."""
    msg = user_message.lower()
    if "pending" in msg or "status" in msg:
        pending_count = Issue.objects.filter(status=Issue.Status.PENDING).count()
        return f"System Stats: There are {pending_count} pending issues. Use the dashboard to see full details."
    
    if reason == "throttled":
        return "AI service is currently throttled due to too many errors. Please try again in a few minutes."
    
    return "AI service temporarily unavailable. Please try again."

def build_chat_reply(user, user_message, context=None, session_key=None):
    """Harden Chat Logic with System Awareness using unified CivicAIAssistant."""
    cb_key = "openai_circuit_breaker"
    failures = cache.get(cb_key, 0)
    
    if failures >= 5:
        logger.warning(f"Circuit Breaker OPEN for user {user.id}. Failures: {failures}")
        return {"success": True, "reply": ai_fallback_reply(user_message, reason="throttled"), "is_fallback": True}

    try:
        from ai.assistant import CivicAIAssistant
        assistant = CivicAIAssistant()
        role = getattr(user, 'role', 'citizen')
        
        # Enrich context with user's issues if relevant
        enriched_context = {"page_context": context}
        query_lower = user_message.lower()
        if any(w in query_lower for w in ["status", "complaint", "issue", "my report", "what happened"]):
            # Use a more efficient query to get recent issues
            issues = Issue.objects.filter(reported_by=user).only('id', 'title', 'status', 'created_at').order_by("-created_at")[:5]
            enriched_context["user_issues"] = [
                {
                    "id": i.id, 
                    "title": i.title, 
                    "status": i.get_status_display() if hasattr(i, 'get_status_display') else i.status, 
                    "created_at": i.created_at.strftime("%Y-%m-%d")
                }
                for i in issues
            ]
        
        # Use the unified pipeline for identical logic
        ai_result = assistant.process_input(user_message, user_role=role, context=enriched_context)
        
        # Reset circuit breaker
        cache.delete(cb_key)
        
        reply = ai_result.get("response", "I am analyzing your request.")
        AIChat.objects.create(user=user, role="assistant", message=reply)
        
        return {"success": True, "reply": reply}

    except Exception as e:
        new_failures = failures + 1
        cache.set(cb_key, new_failures, 300) # Circuit stays open for 5 mins
        logger.error(f"AI API Error: {str(e)}")
        
        return {"success": True, "reply": ai_fallback_reply(user_message), "is_fallback": True}

# (Existing validate_and_execute_action and other internal helpers remain unchanged for safety)
def validate_action_schema(intent, params):
    if intent not in ALLOWED_ACTIONS_SCHEMA: return False, f"Unknown action: {intent}"
    for field in ALLOWED_ACTIONS_SCHEMA[intent]:
        if field not in params: return False, f"Missing field: {field}"
    return True, None

def validate_and_execute_action(user, action_token, session_hash=None):
    try:
        return _execute_sequenced_action(user, action_token, session_hash)
    except Exception as e:
        logger.exception("Execution fail")
        return {"success": False, "message": str(e)}

def _execute_sequenced_action(user, action_token, session_hash=None):
    try:
        unsigned_payload = signer.unsign(action_token)
    except BadSignature:
        return {"success": False, "message": "Invalid token."}

    token_parts = unsigned_payload.split(":")
    if user.id != int(token_parts[0]): return {"success": False, "message": "User mismatch."}
    if session_hash and token_parts[4] != session_hash: return {"success": False, "message": "Session invalid."}
    
    intent = token_parts[1]
    
    try:
        log = AIActionLog.objects.get(action_token=action_token)
        if log.status != "pending": return {"success": False, "message": "Already processed."}
    except AIActionLog.DoesNotExist: return {"success": False, "message": "Log missing."}

    if intent not in ROLE_PERMISSIONS.get(user.role, []):
        return {"success": False, "message": "Permission denied."}

    with transaction.atomic():
        log = AIActionLog.objects.select_for_update().get(id=log.id)
        params = log.params
        issue = Issue.objects.select_for_update().get(id=params["issue_id"])

        if intent == "assign_officer":
            officer = OfficerProfile.objects.get(id=params["officer_id"])
            issue.assigned_to = officer
            issue.status = Issue.Status.ASSIGNED
            res_msg = f"Assigned to {officer.user.username}"
        elif intent == "mark_resolved":
            issue.status = Issue.Status.RESOLVED
            issue.resolved_at = timezone.now()
            issue.resolved_by = user
            res_msg = "Resolved."
        
        issue.save()
        log.status = "success"
        log.execution_result = {"message": res_msg}
        log.save()
        return {"success": True, "message": res_msg}

def get_proactive_insights(user):
    try:
        pending = Issue.objects.filter(status="pending").count()
        critical = Issue.objects.filter(priority="high").count()
        if critical > 5: return "⚠️ High critical load."
        return "✅ System stable."
    except Exception: return "⚠️ Analytics offline."
