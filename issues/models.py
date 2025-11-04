from django.db import models
from accounts.models import Citizen

STATUS_CHOICES = [
    ('Pending', 'Pending'),
    ('In Progress', 'In Progress'),
    ('Resolved', 'Resolved'),
]

class Issue(models.Model):
    citizen = models.ForeignKey(Citizen, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    description = models.TextField()
    category = models.CharField(max_length=100, default='General')
    location = models.CharField(max_length=255, blank=True, null=True)  # ✅ Added
    photo1 = models.ImageField(upload_to='issue_photos/', blank=True, null=True)  # ✅ Added
    photo2 = models.ImageField(upload_to='issue_photos/', blank=True, null=True)  # ✅ Added
    photo3 = models.ImageField(upload_to='issue_photos/', blank=True, null=True)  # ✅ Added
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} ({self.status})"
