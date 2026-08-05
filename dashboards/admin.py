from django.contrib import admin
from .models import Announcement

@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ("title", "created_by", "is_approved", "created_at", "expires_at")
    list_filter = ("is_approved", "created_at", "expires_at")
    search_fields = ("title", "content")
