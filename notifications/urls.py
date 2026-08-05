from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    path('api/list/', views.get_notifications, name='list'),
    path('api/mark-read/<int:notification_id>/', views.mark_as_read, name='mark_read'),
]
