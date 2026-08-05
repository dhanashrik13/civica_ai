from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.account.utils import user_field
from django.utils.text import slugify
from accounts.models import User
import random
import string

class MySocialAccountAdapter(DefaultSocialAccountAdapter):
    def pre_social_login(self, request, sociallogin):
        """Link existing users with same email automatically."""
        if sociallogin.is_existing:
            return
        
        email = sociallogin.user.email
        if email:
            try:
                user = User.objects.get(email=email)
                sociallogin.connect(request, user)
            except User.DoesNotExist:
                pass

    def generate_unique_username(self, email, name):
        """Generate a safe, unique, slug-based username."""
        base = ""
        if name:
            base = slugify(name)
        if not base and email:
            base = slugify(email.split('@')[0])
        if not base:
            base = "user"

        username = base
        count = 1
        while User.objects.filter(username=username).exists():
            # Add random suffix or sequence for uniqueness
            suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
            username = f"{base}-{suffix}"
            if count > 10: # Safety break
                username = f"{base}-{random.randint(1000, 9999)}"
                break
            count += 1
        return username

    def populate_user(self, request, sociallogin, data):
        """Populate user fields from social data."""
        user = super().populate_user(request, sociallogin, data)
        
        email = data.get('email')
        if not email:
            from django.core.exceptions import ValidationError
            raise ValidationError("Email is required for Google login.")

        # Ensure unique username
        name = data.get('name') or f"{data.get('first_name', '')} {data.get('last_name', '')}".strip()
        if not user.username or User.objects.filter(username=user.username).exists():
            user.username = self.generate_unique_username(email, name)

        # Populate full name
        if not user.full_name:
            user_field(user, 'full_name', name or user.username)
        
        return user

    def save_user(self, request, sociallogin, form=None):
        """Set default production fields for new users."""
        user = super().save_user(request, sociallogin, form)
        
        # Default citizen role and active status
        user.role = 'citizen'
        user.is_active = True
        user.is_approved = True
        user.save()
        return user
