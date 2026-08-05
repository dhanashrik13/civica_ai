from django.apps import AppConfig
from django.db.models.signals import post_migrate

def setup_site(sender, **kwargs):
    from django.contrib.sites.models import Site
    Site.objects.update_or_create(
        id=1,
        defaults={'domain': '127.0.0.1:8000', 'name': 'localhost'}
    )

def social_user_setup(sender, request, sociallogin, **kwargs):
    user = sociallogin.user
    if not user.pk:  # New user
        user.role = "citizen"
        user.is_approved = True  # Trusting Google auth for citizen role
        user.is_active = True

class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'

    def ready(self):
        post_migrate.connect(setup_site, sender=self)
        from allauth.socialaccount.signals import pre_social_login
        pre_social_login.connect(social_user_setup)
