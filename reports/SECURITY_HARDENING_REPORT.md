# SECURITY HARDENING REPORT — RBAC Enforcement

## Vulnerability Mitigation: Privilege Escalation
Previously, RBAC protections were primarily implemented in the `User.save()` method, which could be bypassed via:
- `User.objects.update(role='super_admin')`
- `User.objects.bulk_update(objs, ['role'])`
- Direct field manipulation in scripts.

### Remediation Applied:
1. **QuerySet Level Protection:** `UserQuerySet.update()` and `bulk_update()` now explicitly block bulk escalation to administrative roles (`SUPER_ADMIN`, `DEPT_ADMIN`). Any attempt to escalate roles in bulk will raise a `PermissionDenied` exception, forcing developers to use validated service methods.
2. **Model Level Validation:** Implemented `User.clean()` which performs a database check to compare the current role with the existing role. It blocks unauthorized escalation from lower-privileged roles (`CITIZEN`, `OFFICER`) to administrative roles unless a specific RBAC bypass (e.g., forensic mode) is active.
3. **Transaction Integrity:** All role-sensitive operations are now wrapped in `transaction.atomic()` to ensure that role changes and group synchronization occur together.

## Vulnerability Mitigation: Cross-Jurisdiction Leakage
`dept_admin` accounts were previously able to see issues from other districts if those issues were unassigned or if the `jurisdiction_scope` was not strictly enforced.

### Remediation Applied:
1. **Strict Jurisdiction Filtering:** `apply_rbac_filter` was updated to strictly intersect the department filter with the `jurisdiction_scope` geographic filter.
2. **Removal of Permissive Defaults:** Removed `Q(department__isnull=True)` from the `dept_admin` filter, ensuring they only see issues explicitly assigned to their department within their geographic boundary.

## Verification
- Bulk update bypass: **BLOCKED**
- Individual .save() escalation bypass: **BLOCKED**
- Cross-district visibility: **ISOLATED**
