from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from accounts.views import redirect_dashboard

from django.shortcuts import redirect

urlpatterns = [
    path("i18n/", include("django.conf.urls.i18n")),
    path("admin/", admin.site.urls),
    path("login/", lambda r: redirect("accounts:login"), name="login"),
    path("redirect-dashboard/", redirect_dashboard, name="redirect_dashboard"),
    path("", include(("landing.urls", "landing"), namespace="landing")),
    path("accounts/", include(("accounts.urls", "accounts"), namespace="accounts")),
    path("issues/", include(("issues.urls", "issues"), namespace="issues")),
    path("citizen/", include("citizen.urls", namespace="citizen")),
    path("dashboard/", include(("dashboards.urls", "dashboards"), namespace="dashboards")),
    path("assistant/", include(("assistant.urls", "assistant"), namespace="assistant")),
    path("notifications/", include("notifications.urls", namespace="notifications")),
    path("ai-standalone/", include("ai.urls", namespace="ai_standalone")),
    path("accounts/social/", include("allauth.urls")), # REQUIRED for Google OAuth
    path("", include("django_prometheus.urls")),
]

handler404 = 'django.views.defaults.page_not_found'
handler500 = 'django.views.defaults.server_error'

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

