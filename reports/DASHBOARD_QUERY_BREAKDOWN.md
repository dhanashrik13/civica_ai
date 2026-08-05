# DASHBOARD QUERY BREAKDOWN

## 1. QUERY FORENSICS
The citizen reports dashboard uses the following logic:

**File**: `dashboards/services.py`
**Function**: `get_citizen_reports_context`
**Logic**:
```python
reports_qs = apply_rbac_filter(Issue.objects.all(), user).order_by("-created_at")
```

**RBAC Filter** (`accounts/utils.py`):
```python
if role == "citizen":
    return queryset.filter(reported_by=user)
```

## 2. WHY DASHBOARD RETURNS 0 ROWS
- For a user like `citizen_19`, the `reports_qs` filters the `Issue` table for `reported_by=citizen_19`.
- Since no `Issue` rows exist with `reported_by_id=2745` (citizen_19's ID), the query correctly returns an empty queryset.
- The dashboard display "No reports available" is technically **ACCURATE** according to the database state.

## 3. WHY PROFILE SHOWS 3
- The "3" is a static value stored in `accounts_citizenprofile.total_reports`.
- This value is **UNLINKED** to the actual `issues_issue` table.

**Final Verdict**: The dashboard is correct; the profile counter is a "fake" or stale value left over from a sample data population task.
