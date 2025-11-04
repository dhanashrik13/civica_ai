from functools import wraps
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.hashers import make_password, check_password
from django.db import transaction
from .forms import RegisterForm, LoginForm
from .models import Citizen, Officer, Admin, User
from issues.models import Issue


# -----------------------------
# HOME VIEW
# -----------------------------
def home_view(request):
    return render(request, "accounts/home.html")


# -----------------------------
# ROLE SELECTION (Login/Register)
# -----------------------------
def choose_role(request, action):
    """
    Handles both login and registration role selection.
    For registration → show only Citizen.
    For login → show all three roles.
    """
    request.session["action"] = action  # 'login' or 'register'

    if request.method == "POST":
        role = request.POST.get("role")
        if role:
            request.session["chosen_role"] = role
            if action == "register":
                return redirect("accounts:register", role=role)
            else:
                return redirect("accounts:login", role=role)

    # Render separate templates for clarity
    if action == "register":
        return render(request, "accounts/role_selection_register.html", {"action": action})
    else:
        return render(request, "accounts/role_selection_login.html", {"action": action})


# -----------------------------
# REGISTRATION (Citizen only)
# -----------------------------

from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.hashers import make_password
from django.db import IntegrityError
from .models import Citizen


@transaction.atomic
def register_view(request, role):
    if request.method == "POST":
        username = request.POST.get("username")
        email = request.POST.get("email")
        name = request.POST.get("name")
        password = request.POST.get("password")

        try:

            if role != "Citizen":
                messages.error(request, "Invalid role. Registration is allowed only for Citizens.")
                return redirect("accounts:choose_role", action="register")

            # Try to create a new Citizen user
            user = Citizen.objects.create(
                username=username,
                email=email,
                name=name,
                password=make_password(password),
            )

            messages.success(request, "Citizen registered successfully! Please login.")
            return redirect("accounts:login", role=role)

        except IntegrityError:
            # Handle duplicate username/email errors gracefully
            messages.error(request, "Username or Email already exists. Please use a different one.")
            return render(request, "accounts/register.html", {"role": role})

        except Exception as e:
            # Catch unexpected errors
            messages.error(request, f"Something went wrong: {str(e)}")
            return render(request, "accounts/register.html", {"role": role})

    # GET request → show registration form
    return render(request, "accounts/register.html", {"role": role})


# -----------------------------
# LOGIN VIEW
# -----------------------------
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.hashers import check_password
from .models import Citizen, Officer, Admin

def login_view(request, role):
    if request.method == 'POST':
        identifier = request.POST.get('username')
        password = request.POST.get('password')

        model_map = {
            'Citizen': Citizen,
            'Officer': Officer,
            'Admin': Admin,
        }
        model = model_map.get(role)

        if not model:
            messages.error(request, "Invalid role.")
            return redirect('accounts:choose_role', action='login')

        try:
            # Search by email or username
            user = model.objects.filter(email=identifier).first() or model.objects.filter(username=identifier).first()

            if not user:
                messages.error(request, "No account found with that email or username.")
                return render(request, 'accounts/login.html', {'role': role})

            if check_password(password, user.password):
                # Save session data
                request.session['user_id'] = user.id
                request.session['username'] = user.username
                request.session['role'] = role
                request.session.set_expiry(86400 * 7)  # 7 days session expiry

                messages.success(request, f"Welcome, {user.username}!")

                # ✅ Direct redirect to dashboards based on role
                if role == 'Citizen':
                    return redirect('dashboards:citizen_dashboard')
                elif role == 'Officer':
                    return redirect('dashboards:officer_dashboard')
                elif role == 'Admin':
                    return redirect('dashboards:admin_dashboard')

            else:
                messages.error(request, "Incorrect password.")
                return render(request, 'accounts/login.html', {'role': role})

        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
            return render(request, 'accounts/login.html', {'role': role})

    return render(request, 'accounts/login.html', {'role': role})


# -----------------------------
# ROLE DASHBOARD (After Login)
# -----------------------------
def role_dashboard(request):
    if "user_id" not in request.session:
        messages.error(request, "You must log in first.")
        return redirect("accounts:choose_role", action="login")

    username = request.session.get('username')
    return render(request, "accounts/role_dashboard.html", {"username": username})


# -----------------------------
# LOGOUT
# -----------------------------
def logout_view(request):
    request.session.flush()
    messages.success(request, "You have been logged out successfully.")
    return redirect("accounts:home")


# -----------------------------
# LOGIN REQUIRED DECORATOR
# -----------------------------
def login_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if "user_id" not in request.session or "role" not in request.session:
            messages.error(request, "You must log in first.")
            return redirect("accounts:choose_role", action="login")
        return view_func(request, *args, **kwargs)
    return wrapper


# -----------------------------
# ADMIN — USER MANAGEMENT
# -----------------------------
@login_required
def manage_users(request):
    citizens = Citizen.objects.all()
    officers = Officer.objects.all()
    admins = Admin.objects.all()
    return render(request, "admin/manage_users.html", {
        "citizens": citizens,
        "officers": officers,
        "admins": admins,
    })


@login_required
def approve_registration(request, user_id, role):
    user = get_object_or_404(User, id=user_id)
    user.is_active = True
    user.save()
    messages.success(request, f"{role} '{user.username}' approved successfully.")
    return redirect("accounts:manage_users")


@login_required
def edit_user(request, user_id, role):
    user = get_object_or_404(User, id=user_id)
    if request.method == "POST":
        user.username = request.POST.get("username")
        user.email = request.POST.get("email")
        user.save()
        messages.success(request, f"{role} '{user.username}' updated successfully.")
        return redirect("accounts:manage_users")
    return render(request, "admin/edit_user.html", {"user": user, "role": role})


@login_required
def deactivate_account(request, user_id, role):
    user = get_object_or_404(User, id=user_id)
    user.is_active = False
    user.save()
    messages.success(request, f"{role} '{user.username}' deactivated successfully.")
    return redirect("accounts:manage_users")


@login_required
def delete_account(request, user_id, role):
    user = get_object_or_404(User, id=user_id)
    user.delete()
    messages.success(request, f"{role} '{user.username}' deleted successfully.")
    return redirect("accounts:manage_users")
