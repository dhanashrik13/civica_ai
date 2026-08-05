from django.db import models
from accounts.models import User

class AIDocument(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    file = models.FileField(upload_to="ai_docs/")
    extracted_text = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)


class AIChat(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20)  # user / assistant
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

class AIActionLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    action_type = models.CharField(max_length=50) # e.g., "assign_officer", "mark_resolved"
    issue_id = models.IntegerField(null=True, blank=True)
    params = models.JSONField(default=dict)
    timestamp = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, default="pending") # pending, success, fail, cancelled, expired
    is_confirmed = models.BooleanField(default=False)
    
    # Audit & Resilience Fields
    action_token = models.CharField(max_length=255, null=True, blank=True, unique=True)
    idempotency_key = models.CharField(max_length=255, null=True, blank=True, unique=True)
    session_hash = models.CharField(max_length=128, null=True, blank=True)
    
    request_payload = models.JSONField(default=dict, blank=True)
    validated_payload = models.JSONField(default=dict, blank=True)
    execution_result = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-timestamp']
