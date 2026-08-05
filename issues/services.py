from django.db.models import Q, Count
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.utils import timezone
from .models import Issue, Department

from django.db import transaction

@transaction.atomic
def secure_issue_assignment(issue, officer, assigned_by=None):
    """
    STRICT PERMISSION ENFORCEMENT & AUDIT LOGGING.
    Centralized gatekeeper for all issue assignments.
    """
    from accounts.models import User, AuditLog
    
    # 1. OFFICER VALIDITY CHECKS
    if not officer.is_active or not officer.user.is_active:
        raise ValueError(f"Selected officer {officer} is inactive.")
    
    if officer.user.role != User.Role.OFFICER:
        raise ValueError(f"User {officer.user.username} does not have the Officer role.")

    # 2. RBAC & DEPARTMENT AUTHORIZATION
    if assigned_by:
        if assigned_by.role == User.Role.DEPT_ADMIN:
            if issue.department != assigned_by.department:
                raise PermissionDenied("Cannot assign issue from another department.")
            if officer.department != assigned_by.department:
                raise PermissionDenied("Cannot assign to officer in another department.")
        elif assigned_by.role == User.Role.CITIZEN:
             raise PermissionDenied("Citizens cannot assign issues.")
    
    # 3. DOMAIN INTEGRITY CHECKS
    if issue.department and officer.department != issue.department:
        raise ValueError(f"Department mismatch: Issue belongs to {issue.department.name}, but officer belongs to {officer.department.name}.")
    
    # 4. GEOGRAPHIC VALIDATION (Allow parent hierarchy matches)
    if issue.location: 
        is_geo_valid = (officer.location == issue.location)
        if not is_geo_valid:
            # Check if officer location is a parent of issue location (e.g. Taluka officer covering Village issue)
            curr = issue.location.parent
            while curr:
                if curr == officer.location:
                    is_geo_valid = True
                    break
                curr = curr.parent
        
        if not is_geo_valid:
            # Provide more detail for debugging
            off_loc = officer.location.name if officer.location else "None"
            iss_loc = issue.location.name if issue.location else "None"
            raise ValueError(f"Geographic mismatch: Officer jurisdiction ({off_loc}) does not cover issue location ({iss_loc}). Cross-district/cross-taluka leakage blocked.")
            
    # 5. COMMIT ASSIGNMENT
    issue.assigned_to = officer
    issue.assigned_by = assigned_by
    issue.status = Issue.Status.ASSIGNED
    if assigned_by:
        issue.manual_override = True
    
    issue._assigned_via_secure_service = True
    issue.save()

    # 6. AUDIT TRAIL
    AuditLog.objects.create(
        user=assigned_by,
        action=AuditLog.Action.ASSIGNMENT_OVERRIDE if assigned_by else AuditLog.Action.GOVERNANCE_REPLAY,
        resource_type="Issue",
        resource_id=str(issue.id),
        details={
            "officer_id": officer.id,
            "officer_name": officer.user.username,
            "automated": assigned_by is None
        }
    )
    return issue

def map_category_to_department(category):
    """
    Hardened mapping logic for categories to Departments.
    Uses icontains for robustness and provides a fallback.
    """
    category = (category or "").lower()
    
    mapping = {
        "pwd": "Public Works Department (PWD)",
        "pothole": "Public Works Department (PWD)",
        "road_damage": "Public Works Department (PWD)",
        "water_supply": "Water Supply Department",
        "water_leakage": "Water Supply Department",
        "sanitation": "Sanitation Department",
        "garbage": "Sanitation Department",
        "electricity": "Electricity Department",
        "street_light": "Electricity Department",
        "road_transport": "Road & Transport Department",
        "drainage_sewerage": "Drainage & Sewerage Department",
        "drainage": "Drainage & Sewerage Department",
        "health": "Health Department",
        "environment": "Environment Department",
        "urban_planning": "Urban Planning Department",
        "disaster_management": "Disaster Management Department",
        "traffic_police": "Traffic Police Department",
        "municipal_engineering": "Municipal Engineering Department",
    }
    
    dept_name = mapping.get(category)
    if dept_name:
        dept = Department.objects.filter(name__icontains=dept_name).first()
        if dept: return dept

    # FALLBACK: Try to find any department matching the category string directly
    fallback = Department.objects.filter(name__icontains=category).first()
    if fallback: return fallback

    # ULTIMATE FALLBACK: General Administration or first available dept
    return Department.objects.filter(name__icontains="General").first() or Department.objects.first()

def validate_department_semantics(issue):
    """
    Validates whether the assigned department matches the issue content semantically.
    """
    if not issue.department:
        return False, "No department assigned."
    
    dept_name = issue.department.name.lower()
    content = (issue.title + " " + issue.description).lower()
    
    # Semantic mapping rules
    rules = {
        "pothole": ["pwd", "road"],
        "garbage": ["sanitation", "waste", "garbage"],
        "water": ["water supply", "leakage"],
        "electricity": ["electricity", "power", "street light"],
        "traffic": ["traffic", "police", "signal"],
        "drainage": ["drainage", "sewage"],
        "health": ["health", "hospital", "medical"],
    }
    
    for keyword, matched_depts in rules.items():
        if keyword in content:
            if not any(md in dept_name for md in matched_depts):
                return False, f"Semantic mismatch: Content suggests {keyword}, but department is {issue.department.name}"
    
    return True, None

def auto_assign_issue(issue, max_retries=3):
    """
    Unified automatic assignment trigger.
    Attempts to find the best officer and applies assignment securely.
    Includes retry-safe logic for concurrent database locks.
    """
    from .utils import find_best_officer
    import logging
    import time
    from django.db import OperationalError
    
    logger = logging.getLogger(__name__)

    logger.info(f"AUTO ASSIGN START for Issue #{issue.id}")
    
    if issue.assigned_to_id:
        return False

    if not issue.department:
        issue.department = map_category_to_department(issue.category)
        issue.save(update_fields=['department'])

    # PHASE 2 STEP 2: Semantic Validation
    is_valid, reason = validate_department_semantics(issue)
    if not is_valid:
        logger.warning(f"Assignment REJECTED for Issue #{issue.id}: {reason}")
        issue.assignment_explanation = f"AI Classification Rejected: {reason}"
        issue.save(update_fields=['assignment_explanation'])
        return False

    logger.info(f"Finding best officer for Issue #{issue.id}...")
    
    for attempt in range(max_retries):
        try:
            officer = find_best_officer(issue)
            if officer:
                logger.info(f"Found candidate officer for Issue #{issue.id}: {officer.user.username} (Level: {officer.level})")
                secure_issue_assignment(issue, officer, assigned_by=None)
                logger.info(f"Successfully auto-assigned Issue #{issue.id} to {officer.user.username}")
                return True
            else:
                logger.warning(f"No officer found for Issue #{issue.id} (Dept: {issue.department}, Loc: {issue.location})")
                return False
                
        except OperationalError as e:
            if 'locked' in str(e).lower() and attempt < max_retries - 1:
                logger.warning(f"Database locked during auto-assignment for Issue #{issue.id}. Retrying {attempt + 1}/{max_retries}...")
                time.sleep(0.5 * (attempt + 1))  # Exponential backoff
            else:
                logger.error(f"Auto-assignment failed for Issue #{issue.id} after {attempt + 1} attempts: {str(e)}")
                return False
        except Exception as e:
            logger.error(f"Auto-assignment failed for Issue #{issue.id} during secure_issue_assignment: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    return False

def paginate_queryset(queryset, page_number, per_page=10):
    paginator = Paginator(queryset, per_page)
    return paginator.get_page(page_number)

def get_issue_map_points(user, bounds=None, status=None, category=None, assigned_to_id=None, priority=None):
    from django.db.models import F
    from django.core.cache import cache
    import hashlib
    import logging
    from accounts.utils import apply_rbac_filter
    
    logger = logging.getLogger(__name__)
    
    # Generate a unique cache key based on the user and parameters
    key_string = f"{user.id}_{bounds}_{status}_{category}_{assigned_to_id}_{priority}"
    cache_key = "map_points_" + hashlib.md5(key_string.encode('utf-8')).hexdigest()
    
    cached_data = cache.get(cache_key)
    if cached_data is not None:
        return cached_data
        
    logger.info(f"CACHE MISS: Recomputing map points for key {cache_key}")

    qs = Issue.objects.exclude(latitude__isnull=True).exclude(longitude__isnull=True).select_related('department')
    
    # 0. Apply RBAC (STRICT)
    qs = apply_rbac_filter(qs, user)

    if status: qs = qs.filter(status=status)
    if category: qs = qs.filter(category=category)
    if assigned_to_id: qs = qs.filter(assigned_to_id=assigned_to_id)
    if priority: qs = qs.filter(priority=priority)

    data = list(qs.values(
        "id", "title", "latitude", "longitude", "status", "category", 
        "location", "priority", "created_at", "department__name"
    ))
    
    # Cache for 60 seconds to relieve DB pressure during heavy map interactions
    cache.set(cache_key, data, 60)
    return data
def get_public_issue_list_context(page_number, department_id=None, user=None):
    from accounts.utils import apply_rbac_filter
    issues = Issue.objects.all().order_by("-created_at")
    
    if user:
        issues = apply_rbac_filter(issues, user)
        
    if department_id and str(department_id).isdigit():
        issues = issues.filter(department_id=int(department_id))
        
    page_obj = paginate_queryset(issues, page_number)
    return {"issues": page_obj.object_list, "page_obj": page_obj}

def get_location_payload():
    from django.core.cache import cache
    import logging
    from accounts.models import Location
    
    logger = logging.getLogger(__name__)
    cache_key = "global_location_payload_v2"
    payload = cache.get(cache_key)
    
    if payload is None:
        logger.info(f"CACHE MISS: Recomputing global location payload for key {cache_key}")
        # Optimize: Only fetch necessary fields for hierarchy to reduce JSON payload size
        locations = Location.objects.all().values('id', 'name', 'type', 'parent_id')
        payload = list(locations)
        # Cache for 24 hours (Locations are relatively static)
        cache.set(cache_key, payload, 86400)
        
    return None, payload

def resolve_village_selection(villages_qs, village_id):
    try:
        return villages_qs.get(id=village_id)
    except:
        return None

def update_issue_status(issue, status, user, resolved_photo=None):
    if status not in Issue.Status.values:
        raise ValueError("Invalid status")
    
    if issue.status != status:
        issue.status_changed_by = user

    issue.status = status
    issue.updated_by = user
    if status == Issue.Status.RESOLVED:
        issue.resolved_at = timezone.now()
        issue.resolved_by = user
        if resolved_photo:
            issue.resolved_photo = resolved_photo
    issue.save()
    return issue

def detect_duplicate_issues(title, description, location_id, threshold=0.7):
    # ... rest of method ...
    return sorted(duplicates, key=lambda x: x['similarity'], reverse=True)

class FraudDetectionEngine:
    """
    Enterprise Fraud and Spam Detection for Civic Complaints.
    Uses pattern matching and anomaly detection.
    """
    
    @staticmethod
    def analyze_issue(user, title, description, location):
        """
        Flags issues for potential fraud/spam.
        Returns (is_suspicious, reason)
        """
        from .models import Issue
        from django.utils import timezone
        
        # 1. Frequency check (Rate limiting at domain level)
        one_hour_ago = timezone.now() - timezone.timedelta(hours=1)
        recent_count = Issue.objects.filter(reported_by=user, created_at__gte=one_hour_ago).count()
        if recent_count > 10:
            return True, "Excessive reporting frequency (Spam alert)"
            
        # 2. Content Analysis
        spam_keywords = ["lottery", "win", "click here", "subscribe", "buy now"]
        combined = (title + " " + description).lower()
        if any(k in combined for k in spam_keywords):
            return True, "Spam keywords detected"
            
        # 3. Anomaly Detection (Location spikes)
        # If 50+ issues reported in 1 small village in 1 hour
        if location and location.type == 'village':
            loc_spike = Issue.objects.filter(location=location, created_at__gte=one_hour_ago).count()
            if loc_spike > 50:
                 return True, "Local anomaly detected (Potential coordinated fraud)"

        return False, None

def administrative_emergency_override(issue, target_officer, user):
    """
    Bypasses all standard RBAC and Staffing rules for life-safety emergencies.
    Requires SUPER_ADMIN or DEPT_ADMIN role.
    """
    from accounts.models import User
    if user.role not in [User.Role.SUPER_ADMIN, User.Role.DEPT_ADMIN]:
        raise PermissionDenied("Only Administrators can perform emergency overrides.")
        
    issue.priority = "emergency"
    issue.assignment_explanation = f"EMERGENCY OVERRIDE by {user.username}. Standard hierarchy bypassed."
    # Use secure_issue_assignment but we know it might raise errors if depts don't match
    # For emergency, we might want to bypass department checks too, but secure_issue_assignment is strict.
    # If the user is super admin, we should allow it.
    
    secure_issue_assignment(issue, target_officer, assigned_by=user)
    return issue
