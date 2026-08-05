import time
import hashlib
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.core.cache import cache
from django.conf import settings
from .models import AIChat, AIActionLog
from .services import build_chat_reply, get_proactive_insights, validate_and_execute_action, send_to_monitoring_service
from .tasks import execute_ai_action_task

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    return x_forwarded_for.split(',')[0] if x_forwarded_for else request.META.get('REMOTE_ADDR')

def check_global_throttle():
    """GLOBAL THROTTLING: Max 100 system-wide AI requests per minute."""
    key = "global_ai_throttle"
    count = cache.get(key, 0)
    if count >= 100:
        return False
    cache.set(key, count + 1, 60)
    return True

def rate_limit_ai(request):
    """Hard rate limit per user and IP."""
    user_id = request.user.id if request.user.is_authenticated else "anon"
    ip = get_client_ip(request)
    now = time.time()
    
    for key in [f"ai_limit_user_{user_id}", f"ai_limit_ip_{ip}"]:
        reqs = [r for r in cache.get(key, []) if now - r < 60]
        if len(reqs) >= 15: return False 
        reqs.append(now)
        cache.set(key, reqs, 60)
    return True

@login_required
def ai_assistant(request):
    """ASYNC-READY AI ENTRY POINT"""
    if request.method == "POST":
        if not check_global_throttle() or not rate_limit_ai(request):
            return JsonResponse({
                "success": False,
                "reply": "System busy. Please try again in a minute.",
                "error_code": "THROTTLED"
            }, status=429)

        user_message = request.POST.get("message", "").strip()
        context = request.POST.get("context", "Dashboard")
        
        if request.POST.get("proactive") == "true":
            return JsonResponse({"success": True, "reply": get_proactive_insights(request.user)})

        if not user_message:
            return JsonResponse({"success": False, "reply": "Empty message."}, status=400)
            
        try:
            if not request.session.session_key:
                request.session.create()
            
            result = build_chat_reply(
                request.user, 
                user_message, 
                context=context, 
                session_key=request.session.session_key
            )
            return JsonResponse(result)
        except Exception as e:
            send_to_monitoring_service("view_failure", {"error": str(e), "user_id": request.user.id})
            return JsonResponse({
                "success": False, 
                "reply": "System timeout. Fallback enabled.",
                "error_code": "INTERNAL_ERROR"
            }, status=500)

    chats = AIChat.objects.filter(user=request.user).order_by("created_at")[:20]
    return render(request, "assistant/assistant_refactored.html", {"chats": chats})

@login_required
def debug_ai_status(request):
    """DEBUG: Check AI Key and Circuit Breaker Status."""
    if not request.user.is_superuser:
        return JsonResponse({"error": "Unauthorized"}, status=403)
        
    cb_key = "openai_circuit_breaker"
    api_key = getattr(settings, "OPENAI_API_KEY", "")
    
    return JsonResponse({
        "api_key_configured": bool(api_key),
        "api_key_prefix": api_key[:8] + "..." if api_key else "NONE",
        "circuit_breaker_failures": cache.get(cb_key, 0),
    })

@login_required
def reset_ai_circuit(request):
    """DEBUG: Reset AI Circuit Breaker."""
    if not request.user.is_superuser:
        return JsonResponse({"error": "Unauthorized"}, status=403)
    
    cache.delete("openai_circuit_breaker")
    return JsonResponse({"message": "Circuit breaker reset."})

@login_required
def confirm_ai_action(request):
    """ASYNC ACTION DISPATCHER"""
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Invalid method."}, status=405)
    
    token = request.POST.get("action_token")
    if not token:
        return JsonResponse({"success": False, "message": "Token missing."}, status=400)
    
    try:
        session_hash = hashlib.sha256(str(request.session.session_key).encode()).hexdigest()
        log = AIActionLog.objects.get(action_token=token, user=request.user, status="pending")
        execute_ai_action_task.delay(request.user.id, token, session_hash)
        
        return JsonResponse({
            "success": True, 
            "status": "processing",
            "message": "Action dispatched for background execution.",
            "action_token": token
        })
    except AIActionLog.DoesNotExist:
        return JsonResponse({"success": False, "message": "Action not found or already processed."}, status=404)
    except Exception as e:
        return JsonResponse({"success": False, "message": "Dispatch failed.", "error": str(e)}, status=500)

@login_required
def get_action_status(request):
    """POLLING ENDPOINT for async task state tracking."""
    token = request.GET.get("action_token")
    if not token:
        return JsonResponse({"success": False, "message": "Missing token."}, status=400)
    
    try:
        log = AIActionLog.objects.get(action_token=token, user=request.user)
        return JsonResponse({
            "success": True,
            "status": log.status,
            "message": log.execution_result.get("message") if log.status == "success" else log.error_message,
            "data": log.execution_result
        })
    except AIActionLog.DoesNotExist:
        return JsonResponse({"success": False, "message": "Action record not found."}, status=404)

@login_required
def cancel_ai_action(request):
    """SAFE CANCELLATION"""
    token = request.POST.get("action_token")
    try:
        AIActionLog.objects.filter(action_token=token, user=request.user, status="pending").update(status="cancelled")
        return JsonResponse({"success": True, "message": "Action cancelled successfully."})
    except Exception:
        return JsonResponse({"success": False, "message": "Cancel failed."}, status=500)
