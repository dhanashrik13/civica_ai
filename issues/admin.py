from django.contrib import admin
from .models import Issue, Comment
from accounts.models import IssueImage, OfficerProfile

@admin.register(Issue)
class IssueAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "category",
        "governance_scope",
        "status",
        "reported_by",
        "assigned_to",
        "location",
        "created_at",
        "updated_at",
    )
    list_filter = ("status", "category", "governance_scope", "priority", "department")
    search_fields = ("title", "description", "location__name")
    date_hierarchy = "created_at"

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "assigned_to":
            # Try to get the object ID from the URL
            resolved = request.resolver_match
            if resolved and 'object_id' in resolved.kwargs:
                try:
                    obj = Issue.objects.get(pk=resolved.kwargs['object_id'])
                    if obj.department and obj.location:
                        kwargs["queryset"] = OfficerProfile.objects.filter(
                            department=obj.department, 
                            location=obj.location,
                            is_active=True
                        )
                    elif obj.department:
                        kwargs["queryset"] = OfficerProfile.objects.filter(department=obj.department, is_active=True)
                    else:
                        kwargs["queryset"] = OfficerProfile.objects.none()
                except Issue.DoesNotExist:
                    pass
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("id", "issue", "user", "created_at")
    list_filter = ("created_at",)
    search_fields = ("text",)

admin.site.register(IssueImage)
