from django.urls import path
from dashboards import views

app_name = "citizen"

urlpatterns = [
    path("", views.citizen_dashboard, name="citizen_dashboard"),
    path("reports/", views.citizen_reports, name="citizen_reports"),
    path("edit-profile/", views.citizen_edit_profile, name="citizen_edit_profile"),
    path("ai-assistant/", views.citizen_ai_assistant, name="citizen_ai_assistant"),
    path("help-support/", views.citizen_help_support, name="citizen_help_support"),
    path("issues/<int:pk>/delete/", views.delete_issue, name="citizen_delete_issue"),
    path("issues/<int:issue_id>/", views.citizen_issue_detail, name="citizen_issue_detail"),
    path("issue-map/", views.citizen_issue_map, name="citizen_issue_map"),
    path("department/<int:dept_id>/", views.department_detail, name="department_detail"),
]