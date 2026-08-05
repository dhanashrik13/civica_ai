from django.db.models import Q

def reverse_geocode_coordinates(lat, lon):
    """
    Returns city and state from coordinates.
    Currently a placeholder implementation for stability.
    """
    # In a real app, you would use geopy or a geocoding API here.
    return {
        "city": "Unknown",
        "state": "Unknown",
        "address": ""
    }

def apply_rbac_filter(queryset, user):
    """
    Explicitly applies RBAC filtering to a queryset based on the user's role.
    This should be called in views or services, NOT in the model/manager layer.
    """
    if not user or not user.is_authenticated:
        return queryset.none()
        
    model_name = queryset.model.__name__
    role = getattr(user, 'role', None)

    # Prevent N+1 on Issue queries
    if model_name == "Issue":
        queryset = queryset.select_related(
            "reported_by__citizen_profile",
            "reported_by__officer",
            "reported_by__admin_profile",
            "assigned_to__user",
            "assigned_to__department",
            "assigned_to__location",
            "department",
            "location"
        )
    elif model_name == "User":
        queryset = queryset.select_related("citizen_profile", "officer", "admin_profile")

    if getattr(user, 'is_superuser', False) or role == "super_admin":
        return queryset
        
    if model_name == "Issue":
        if role == "dept_admin":
            # Check jurisdiction_scope for isolation
            admin_profile = getattr(user, 'admin_profile', None)
            jurisdiction = admin_profile.jurisdiction_scope if admin_profile else None
            
            # Base filter: Only their own department
            dept_id = admin_profile.department_id if admin_profile else None
            q_filter = Q(department_id=dept_id)
            
            # STRICT ISOLATION: If jurisdiction is set, restrict to that geographic area
            if jurisdiction:
                geo_filter = (
                    Q(district__iexact=jurisdiction) | 
                    Q(taluka__iexact=jurisdiction) | 
                    Q(village__iexact=jurisdiction) |
                    Q(city__iexact=jurisdiction) |
                    Q(ward__iexact=jurisdiction)
                )
                q_filter &= geo_filter
            
            return queryset.filter(q_filter)
        if role == "officer":
            # STRICT: Officers ONLY see their own assigned issues
            return queryset.filter(assigned_to__user=user)
        if role == "citizen":
            return queryset.filter(reported_by=user)
            
    elif model_name == "User":
        if role == "dept_admin":
            admin_profile = getattr(user, 'admin_profile', None)
            dept_id = admin_profile.department_id if admin_profile else None
            # Dept admin can see users in their dept + anyone who reported an issue in their dept
            return queryset.filter(Q(officer__department_id=dept_id) | Q(id=user.id))
        return queryset.filter(id=user.id)
        
    elif model_name == "OfficerProfile":
        queryset = queryset.select_related("user", "department", "location")
        if role == "dept_admin":
            admin_profile = getattr(user, 'admin_profile', None)
            jurisdiction = admin_profile.jurisdiction_scope if admin_profile else None
            dept_id = admin_profile.department_id if admin_profile else None
            q_filter = Q(department_id=dept_id)
            if jurisdiction:
                 q_filter &= Q(district__iexact=jurisdiction) | Q(taluka__iexact=jurisdiction) | Q(city__iexact=jurisdiction)
            return queryset.filter(q_filter)
        if role == "officer":
            return queryset.filter(user=user)
            
    elif model_name == "Comment":
        queryset = queryset.select_related("user__citizen_profile", "user__officer", "user__admin_profile")
        if role == "dept_admin":
            admin_profile = getattr(user, 'admin_profile', None)
            dept_id = admin_profile.department_id if admin_profile else None
            return queryset.filter(issue__department_id=dept_id)
        if role == "officer":
            return queryset.filter(issue__assigned_to__user=user)
        if role == "citizen":
            return queryset.filter(issue__reported_by=user)

    elif model_name == "AssignmentLog":
        queryset = queryset.select_related("officer__user")
        if role == "dept_admin":
            admin_profile = getattr(user, 'admin_profile', None)
            dept_id = admin_profile.department_id if admin_profile else None
            return queryset.filter(officer__department_id=dept_id)
        if role == "officer":
            return queryset.filter(officer__user=user)

    return queryset.none()
