from django.db import models
from django.conf import settings

class Notification(models.Model):
    class Type(models.TextChoices):
        ISSUE_CREATED = 'issue_created', 'Issue Created'
        ISSUE_ASSIGNED = 'issue_assigned', 'Issue Assigned'
        ISSUE_UPDATED = 'issue_updated', 'Issue Updated'
        ISSUE_RESOLVED = 'issue_resolved', 'Issue Resolved'
        PROFILE_UPDATED = 'profile_updated', 'Profile Updated'
        ESCALATION = 'escalation', 'Escalation'

    class Channel(models.TextChoices):
        IN_APP = 'in_app', 'In-App'
        EMAIL = 'email', 'Email'
        SMS = 'sms', 'SMS'

    class Severity(models.TextChoices):
        CRITICAL = 'critical', 'Critical (Immediate Action)'
        HIGH = 'high', 'High'
        MEDIUM = 'medium', 'Medium'
        LOW = 'low', 'Low'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    type = models.CharField(max_length=20, choices=Type.choices, default=Type.ISSUE_UPDATED)
    channel = models.CharField(max_length=10, choices=Channel.choices, default=Channel.IN_APP)
    severity = models.CharField(max_length=10, choices=Severity.choices, default=Severity.MEDIUM, db_index=True)
    related_issue = models.ForeignKey('issues.Issue', on_delete=models.SET_NULL, null=True, blank=True)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    
    # Delivery tracking
    delivery_status = models.CharField(max_length=20, default='pending')
    retry_count = models.IntegerField(default=0)
    error_log = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    idempotency_key = models.CharField(max_length=150, null=True, blank=True, unique=True, help_text="Prevents duplicate notifications")

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.type} for {self.user.username}"
