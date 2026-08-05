from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import role_required
from accounts.services import authenticate_for_role, register_citizen, update_user_profile
from accounts.utils import apply_rbac_filter

User = get_user_model()


def domain_login(request, profile, role):
    from django.contrib.auth import login
    request.session['domain_profile_id'] = profile.id
    request.session['domain_profile_role'] = role
    
    # PHASE 4: Ensure legacy request.user is also authenticated for standard Django decorators
    if hasattr(profile, 'user'):
        login(request, profile.user, backend='django.contrib.auth.backends.ModelBackend')
    
    # STABILIZE: Immediately inject identity into request so redirect_dashboard works in-turn
    if role == 'citizen': request.citizen = profile
    elif role == 'officer': request.officer = profile
    elif role in ['dept_admin', 'super_admin']: request.admin = profile
    
    # FORCE session save to prevent race conditions during immediate redirects
    request.session.save()
    
def domain_logout(request):
    request.session.flush()

def redirect_dashboard(request):
    if hasattr(request, 'officer') and request.officer:
        return redirect('dashboards:officer_dashboard')
    elif hasattr(request, 'admin') and request.admin:
        return redirect('dashboards:admin_dashboard')
    elif hasattr(request, 'citizen') and request.citizen:
        return redirect('dashboards:citizen_dashboard')
    
    # Fallback to legacy
    user = request.user
    if not user.is_authenticated:
        return redirect('accounts:login', role='citizen')

    if hasattr(user, 'officer'):
        return redirect('dashboards:officer_dashboard')
    elif user.role in [User.Role.DEPT_ADMIN, User.Role.SUPER_ADMIN]:
        return redirect('dashboards:admin_dashboard')
    else:
        return redirect('dashboards:citizen_dashboard')


def home_view(request):
    return redirect("landing:home")


def login_redirect_view(request):
    """
    Fallback view for reverse('login') when no role is provided.
    Redirects to the default citizen login.
    """
    return redirect("accounts:login", role=User.Role.CITIZEN)


from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit
from django.core.exceptions import PermissionDenied

@ratelimit(key='ip', rate='10/m', block=True)
@ratelimit(key='post:email', rate='5/m', block=True)
@csrf_protect
def login_view(request, role):
    role = role.lower().strip()
    
    selected_role = request.POST.get("role", role).lower().strip()
    
    if request.method == "POST":
        print(f"DEBUG: Processing login for role: {selected_role}")
        
        roles_to_try = [selected_role]
        if selected_role == "admin":
            roles_to_try = [User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN]
        
        profile = None
        matched_role = None
        for r in roles_to_try:
            profile = authenticate_for_role(
                request,
                request.POST.get("email", "").strip(),
                request.POST.get("password", ""),
                r,
            )
            if profile:
                matched_role = r
                break

        if profile is None:
            messages.error(request, "Invalid email, password, or role.")
            return render(request, "accounts/login_refactored.html", {"role": role})

        if not profile.is_active:
            messages.error(request, "Your account is not active.")
            return render(request, "accounts/login_refactored.html", {"role": role})

        domain_login(request, profile, matched_role)
        request.session.set_expiry(1209600 if request.POST.get("remember_me") else 0)

        return redirect_dashboard(request)

    return render(request, "accounts/login_refactored.html", {"role": role})


from accounts.forms import RegisterForm

def register_view(request):
    if request.method == "POST":
        form = RegisterForm(request.POST, role=User.Role.CITIZEN)
        
        if form.is_valid():
            try:
                profile = register_citizen(form.cleaned_data)
                domain_login(request, profile, 'citizen')
                return redirect_dashboard(request)
            except ValidationError as exc:
                messages.error(request, exc.message)
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.replace('_', ' ').title()}: {error}")

    return render(request, "accounts/register_refactored.html")


from django.views.decorators.http import require_POST

import logging
logger = logging.getLogger(__name__)

# -----------------------------
# LOGOUT
# -----------------------------
@require_POST
def logout_view(request):
    domain_logout(request)
    messages.success(request, "You have been logged out successfully.")
    return redirect("accounts:login")


# -----------------------------
# ADMIN — USER MANAGEMENT
# -----------------------------
@role_required(User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN)
def manage_users(request):
    accessible_users = apply_rbac_filter(User.objects.all(), request.user)
    citizens_qs = accessible_users.filter(role=User.Role.CITIZEN)
    officers_qs = accessible_users.filter(role=User.Role.OFFICER)
    admins_qs = accessible_users.filter(role__in=[User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN])

    return render(
        request,
        "accounts/manage_users.html",
        {
            "citizens": citizens_qs,
            "officers": officers_qs,
            "admins": admins_qs,
        },
    )


@role_required(User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN)
@require_POST
def approve_registration(request, user_id):
    user = get_object_or_404(apply_rbac_filter(User.objects.all(), request.user), id=user_id)

    user.is_active = True
    user.is_approved = True
    user.save()
    messages.success(request, "User approved successfully.")
    return redirect("accounts:manage_users")


from accounts.forms import RegisterForm, UserEditForm, UserProfileForm  # FIXED

@role_required(User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN)
def edit_user(request, user_id):
    user = get_object_or_404(apply_rbac_filter(User.objects.all(), request.user), id=user_id)

    if request.method == "POST":
        # FIXED: Use Django Forms for backend validation and sanitization
        form = UserEditForm(request.POST, request=request)
        if form.is_valid():
            data = form.cleaned_data

            update_user_profile(
                user,
                full_name=data.get("full_name", user.full_name),
                email=data.get("email", user.email),
                phone_no=data.get("phone_no", user.phone_no),
                address=data.get("address", user.address),
            )
            user.username = data.get("username", user.username)
            user.role = data.get("role", user.role)
            user.department = data.get("department", user.department)
            user.is_active = data.get("is_active", user.is_active)
            user.is_approved = data.get("is_approved", user.is_approved)
            user.save()

            messages.success(request, "User updated successfully.")
            return redirect("accounts:manage_users")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.replace('_', ' ').title()}: {error}")

    # Initialize form with current user data
    initial_data = {
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "department": user.department,
        "is_active": user.is_active,
        "is_approved": user.is_approved,
        "phone_no": user.phone_no,
        "address": user.address,
    }
    form = UserEditForm(initial=initial_data, request=request)

    return render(request, "accounts/edit_user.html", {"managed_user": user, "form": form})


@role_required(User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN)
@require_POST
def deactivate_account(request, user_id):
    user = get_object_or_404(apply_rbac_filter(User.objects.all(), request.user), id=user_id)

    user.is_active = False
    user.save()
    messages.success(request, "User deactivated successfully.")
    return redirect("accounts:manage_users")


@role_required(User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN)
@require_POST
def delete_account(request, user_id):
    user = get_object_or_404(apply_rbac_filter(User.objects.all(), request.user), id=user_id)

    user.delete()
    messages.success(request, "User deleted successfully.")
    return redirect("accounts:manage_users")


from notifications.models import Notification

@login_required
def profile_view(request):
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            # Create a notification for the user
            from notifications.tasks import dispatch_notifications
            from notifications.models import Notification
            dispatch_notifications.delay(
                request.user.id,
                Notification.Type.PROFILE_UPDATED,
                "Your profile has been updated successfully!"
            )
            messages.success(request, "Profile updated successfully.")
            return redirect('accounts:profile')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = UserProfileForm(instance=request.user)
    
    return render(request, "accounts/profile.html", {"form": form})
