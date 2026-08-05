from django.urls import path
from . import views

app_name = 'issues'

urlpatterns = [
    path('report/', views.report_issue, name='report_issue'),
    path('<int:pk>/update-status/', views.update_status, name='update_status'),
    path("map/", views.issue_map, name="issue_map"),
    path("map/data/", views.issue_map_data, name="issue_map_data"),
    path('', views.issue_list, name='issue_list'),
    path("issue-detail/<int:pk>/", views.issue_detail_redirect, name="issue_detail_redirect"),
    path("issue/<int:pk>/", views.issue_detail, name="issue_detail"),
    path("resolve-gis/", views.resolve_gis_location, name="resolve_gis"),
]
