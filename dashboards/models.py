from django.db import models
from django.conf import settings
from django.utils import timezone

class Announcement(models.Model):
    title = models.CharField(max_length=200)
    content = models.TextField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="announcements")
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

class DistrictDashboardProjection(models.Model):
    """
    Asynchronous Read Model for high-performance dashboard rendering.
    Updated via IssueEvent stream. Separates Read from Write (CQRS).
    """
    district = models.CharField(max_length=100, db_index=True)
    department = models.ForeignKey("accounts.Department", on_delete=models.CASCADE)
    
    pending_count = models.IntegerField(default=0)
    assigned_count = models.IntegerField(default=0)
    resolved_count = models.IntegerField(default=0)
    high_priority_count = models.IntegerField(default=0)
    
    last_event_id = models.IntegerField(default=0, help_text="Last processed event ID for idempotency")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [['district', 'department']]
        indexes = [
            models.Index(fields=['district', 'department']),
        ]

    def __str__(self):
        return f"Projection: {self.district} | {self.department.name}"

