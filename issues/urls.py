from django.urls import path
from . import views

app_name = 'issues'

urlpatterns = [
    path('report/', views.report_issue, name='report_issue'),
    path('list/', views.issue_list, name='issue_list'),
    path('<int:pk>/', views.issue_detail, name='issue_detail'),
    path('<int:pk>/update-status/', views.update_status, name='update_status'),
    path('<int:pk>/assign/', views.assign_issue, name='assign_issue'),
]
