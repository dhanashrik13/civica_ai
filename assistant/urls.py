from django.urls import path
from . import views

app_name = 'assistant'

urlpatterns = [
    path('', views.ai_assistant, name='ai_assistant'),
    path('confirm/', views.confirm_ai_action, name='confirm_ai_action'),
    path('cancel/', views.cancel_ai_action, name='cancel_ai_action'),
    path('status/', views.get_action_status, name='get_action_status'),
    
    # Debug routes
    path('debug/status/', views.debug_ai_status, name='debug_status'),
    path('debug/reset/', views.reset_ai_circuit, name='debug_reset'),
]
