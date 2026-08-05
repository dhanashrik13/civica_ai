import logging
from django.core.exceptions import PermissionDenied

logger = logging.getLogger('rbac.security')

class RBACPermissions:
    @staticmethod
    def check(user, obj, action):
        if not user or not user.is_authenticated:
            return True
            
        if getattr(user, 'is_superuser', False) or getattr(user, 'role', None) == "super_admin":
            return True

        model_name = obj.__class__.__name__
        
        if model_name == "Issue":
            if action in ["view", "edit"]:
                if getattr(user, 'role', None) == "dept_admin" and obj.department_id == user.department_id:
                    return True
                if getattr(user, 'role', None) == "officer" and obj.assigned_to_id and obj.assigned_to.user_id == user.id:
                    return True
                if getattr(user, 'role', None) == "citizen" and obj.reported_by_id == user.id:
                    return True
            elif action == "delete":
                if getattr(user, 'role', None) == "dept_admin" and obj.department_id == user.department_id:
                    return True
                if getattr(user, 'role', None) == "citizen" and obj.reported_by_id == user.id:
                    return True
                    
        elif model_name == "User":
            if action == "view":
                if getattr(user, 'role', None) == "dept_admin" and obj.department_id == user.department_id:
                    return True
                if user.id == obj.id:
                    return True
            elif action == "edit":
                if getattr(user, 'role', None) == "dept_admin" and obj.department_id == user.department_id and obj.role in ["officer", "citizen"]:
                    return True
                if user.id == obj.id:
                    return True
            elif action == "delete":
                if getattr(user, 'role', None) == "dept_admin" and obj.department_id == user.department_id and obj.role in ["officer", "citizen"]:
                    return True
                
        logger.warning(f"Unauthorized {action} attempt by User {getattr(user, 'id', 'Unknown')} on {model_name} {getattr(obj, 'id', 'New')}")
        raise PermissionDenied(f"You do not have permission to {action} this {model_name}.")

    @staticmethod
    def enforce_audit_integrity(user, obj, old_obj):
        """Enforces that audit fields like created_by cannot be changed."""
        model_name = obj.__class__.__name__
        
        if model_name == "Issue":
            if old_obj.reported_by_id != obj.reported_by_id:
                logger.error(f"Audit Integrity Violation: User {getattr(user, 'id', 'Unknown')} attempted to change reported_by of Issue {obj.id}.")
                raise PermissionDenied("Cannot modify the reporter of an issue.")
            
            if old_obj.created_at != obj.created_at:
                logger.error(f"Audit Integrity Violation: User {getattr(user, 'id', 'Unknown')} attempted to change created_at of Issue {obj.id}.")
                raise PermissionDenied("Cannot modify the creation timestamp.")
