from functools import wraps
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.core.exceptions import PermissionDenied

def role_required(*roles):
    """
    Strict role-based access control.
    Super Admin has access to everything.
    Other roles are restricted to their assigned roles.
    """
    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            user = request.user
            
            # Super Admin bypass
            if user.role == "super_admin":
                return view_func(request, *args, **kwargs)
                
            # Check if user role is in allowed roles
            if user.role in roles:
                return view_func(request, *args, **kwargs)

            messages.error(request, "Access denied: Insufficient permissions.")
            
            # Safe redirect based on role
            try:
                return redirect(user.dashboard_url_name)
            except:
                return redirect("landing:home")

        return wrapped_view
    return decorator

def secure_dept_access(user, department):
    """
    Reusable enforcement for department-level isolation.
    """
    if user.role == "super_admin":
        return True
    if user.role == "dept_admin" and user.department == department:
        return True
    raise PermissionDenied("You do not have access to this department's data.")
