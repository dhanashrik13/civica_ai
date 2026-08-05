from django.urls import path
from . import views

app_name = 'ai_standalone'

urlpatterns = [
    path('suggestions/', views.ai_assistant_suggestions, name='suggestions'),
    path('diagnostic/', views.ai_diagnostic_test, name='diagnostic'),
]
