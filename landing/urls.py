from django.urls import path
from . import views

app_name = "landing"

urlpatterns = [
    path("", views.homepage, name="home"),
    path("about/", views.about, name="about"),
    path("feature/", views.feature, name="feature"),
    path("contact/", views.contact, name="contact"),
    path("docs/", views.documentation, name="documentation"),
    path("quick-start/", views.quick_start, name="quick_start"),
    path("videos/", views.videos, name="videos"),
    path("api-docs/", views.api_docs, name="api_docs"),
    path("privacy/", views.privacy_policy, name="privacy"),
    path("terms/", views.terms_of_service, name="terms"),
    path("support/", views.help_support, name="support"),
    path("faq/", views.faq, name="faq"),
]
