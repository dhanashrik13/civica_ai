import json
import os
import google.generativeai as genai
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.conf import settings
from .assistant import CivicAIAssistant

@csrf_exempt
@require_POST
def ai_assistant_suggestions(request):
    """
    Standalone view for AI Assistant suggestions.
    Isolated from main business logic.
    """
    try:
        data = json.loads(request.body)
        description = data.get("description", "")
        
        role = "citizen"
        if request.user.is_authenticated:
            if hasattr(request.user, 'role'):
                role = request.user.role.lower()
            elif request.user.is_superuser:
                role = "admin"
                
        if not description:
            return JsonResponse({"error": "Description is required"}, status=400)
            
        assistant = CivicAIAssistant()
        suggestions = assistant.process_input(description, user_role=role)
        
        return JsonResponse(suggestions)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"AI Assistant View Failure: {str(e)}", exc_info=True)
        return JsonResponse({
            "error": "AI Assistant is currently unavailable. Please try again later.",
            "is_reliable": False,
            "confidence": 0
        }, status=500)

def ai_diagnostic_test(request):
    """
    Diagnostic view to test AI configuration and connectivity.
    Only accessible by superusers.
    """
    if not request.user.is_superuser:
        return JsonResponse({"error": "Unauthorized"}, status=403)
        
    api_key = getattr(settings, "GOOGLE_GEMINI_API_KEY", None) or os.getenv("GOOGLE_GEMINI_API_KEY")
    
    results = {
        "api_key_configured": bool(api_key),
        "api_key_prefix": api_key[:4] + "..." if api_key else "None",
        "env_var_status": os.getenv("GOOGLE_GEMINI_API_KEY") is not None,
        "settings_status": hasattr(settings, "GOOGLE_GEMINI_API_KEY"),
        "library_version": genai.__version__,
        "test_connection": "Not Attempted"
    }
    
    if api_key:
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content("Ping", generation_config={"max_output_tokens": 5})
            results["test_connection"] = "Success"
            results["response_sample"] = response.text.strip()
        except Exception as e:
            results["test_connection"] = f"Failed: {str(e)}"
            
    return JsonResponse(results)
