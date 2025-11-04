from django.urls import path
from . import views

app_name = "accounts"  # ✅ important for namespacing

urlpatterns = [
    path('', views.home_view, name='home'),
    path('choose_role/<str:action>/', views.choose_role, name='choose_role'),
    path('role_dashboard/', views.role_dashboard, name='role_dashboard'),
    path('register/<str:role>/', views.register_view, name='register'),
    path('login/<str:role>/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
]
