import logging
import time
from contextvars import ContextVar

logger = logging.getLogger('rbac.security')

_user_context = ContextVar("current_user", default=None)
_bypass_rbac_context = ContextVar("bypass_rbac", default=False)
_forensic_mode_context = ContextVar("forensic_mode", default=False)

def set_current_user(user):
    return _user_context.set(user)

def get_current_user():
    return _user_context.get()

def set_bypass_rbac(value=True):
    return _bypass_rbac_context.set(value)

def is_rbac_bypassed():
    return _bypass_rbac_context.get()

def set_forensic_mode(value=True):
    return _forensic_mode_context.set(value)

def is_forensic_mode():
    return _forensic_mode_context.get()

class DomainIdentityMiddleware:
    """
    Centralized Identity Resolver Middleware (Phase 3).
    Bypasses Django's centralized User model for session authentication.
    Injects request.citizen, request.officer, and request.admin based on domain logic.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.citizen = None
        request.officer = None
        request.admin = None
        
        # We also maintain request.user for legacy compatibility (Phase 4)
        if not hasattr(request, 'user'):
            from django.contrib.auth.models import AnonymousUser
            request.user = AnonymousUser()
            
        profile_id = request.session.get('domain_profile_id')
        profile_role = request.session.get('domain_profile_role')
        
        if profile_id and profile_role:
            from accounts.models import CitizenProfile, OfficerProfile, AdminProfile
            try:
                if profile_role == 'citizen':
                    request.citizen = CitizenProfile.objects.get(pk=profile_id)
                    request.user = request.citizen.user # For legacy compatibility
                elif profile_role == 'officer':
                    request.officer = OfficerProfile.objects.get(pk=profile_id)
                    request.user = request.officer.user # For legacy compatibility
                elif profile_role in ['dept_admin', 'super_admin']:
                    request.admin = AdminProfile.objects.get(pk=profile_id)
                    request.user = request.admin.user # For legacy compatibility
            except Exception:
                pass
                
        return self.get_response(request)

class OperationalForensicsMiddleware:

    """
    Forensic Logging for Governance Actions.
    Captures every mutation request for deterministic reconstruction.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == "POST":
            start_time = time.time()
            response = self.get_response(request)
            duration = time.time() - start_time
            
            user = request.user if request.user.is_authenticated else "anonymous"
            logger.info(
                f"[FORENSICS] Action: {request.path} | User: {user} | "
                f"Status: {response.status_code} | Duration: {duration:.4f}s"
            )
            return response
        
        return self.get_response(request)

class RBACMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # STABILIZE: Prefetch profiles on the user object once per request
        if request.user.is_authenticated:
            # We use a simple attribute check to avoid re-prefetching if already done
            if not hasattr(request.user, '_profiles_prefetched'):
                from django.contrib.auth import get_user_model
                User = get_user_model()
                # Force evaluation and caching of profiles
                # select_related on request.user is tricky since it's often a SimpleLazyObject
                # But we can force it here.
                request.user = User.objects.select_related(
                    'officer', 'citizen_profile', 'admin_profile',
                    'officer__department', 'admin_profile__department'
                ).get(pk=request.user.pk)
                request.user._profiles_prefetched = True

        token = set_current_user(request.user)

        # RBAC is generally bypassed for authenticated users in admin or via explicit bypass.
        # We set default bypass to False and let views/managers handle it if they were still using it.
        # But we've removed RBAC from managers, so this is mostly for the .save() hooks.
        bypass_token = set_bypass_rbac(False)
        
        try:
            response = self.get_response(request)
        finally:
            _user_context.reset(token)
            _bypass_rbac_context.reset(bypass_token)
        return response

class bypass_rbac:
    """Context manager for background jobs and scripts to explicitly bypass RBAC hooks."""
    def __enter__(self):
        self.token = set_bypass_rbac(True)
    def __exit__(self, exc_type, exc_val, exc_tb):
        _bypass_rbac_context.reset(self.token)

class forensic_mode:
    """Context manager to suppress side-effects during forensic replay."""
    def __enter__(self):
        self.token = set_forensic_mode(True)
    def __exit__(self, exc_type, exc_val, exc_tb):
        _forensic_mode_context.reset(self.token)
