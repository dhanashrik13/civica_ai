from django.urls import path
from . import views

app_name = "dashboards"

urlpatterns = [
    path('citizen/', views.citizen_dashboard, name='citizen_dashboard'),
    path('citizen/edit/', views.citizen_edit_profile, name='citizen_edit_profile'),

    path('officer/', views.officer_dashboard, name='officer_dashboard'),
    path('admin/', views.admin_dashboard, name='admin_dashboard'),
]

