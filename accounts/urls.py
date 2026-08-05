from django.urls import path
from . import views
from .views import redirect_dashboard

app_name = "accounts"  # ✅ important for namespacing

urlpatterns = [
    path('', views.home_view, name='home'),
    path('register/', views.register_view, name='register'),
    path('login/', views.login_redirect_view, name='login'),
    path("login/<str:role>/", views.login_view, name="login"),
    path('logout/', views.logout_view, name='logout'),
    path('redirect-dashboard/', views.redirect_dashboard, name='redirect_dashboard'),
    path("manage-users/", views.manage_users, name="manage_users"),
    path("manage-users/<int:user_id>/approve/", views.approve_registration, name="approve_registration"),
    path("manage-users/<int:user_id>/edit/", views.edit_user, name="edit_user"),
    path("manage-users/<int:user_id>/deactivate/", views.deactivate_account, name="deactivate_account"),
    path("manage-users/<int:user_id>/delete/", views.delete_account, name="delete_account"),
    path("profile/", views.profile_view, name="profile"),
]
