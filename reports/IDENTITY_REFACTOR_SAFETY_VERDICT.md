# IDENTITY REFACTOR PRODUCTION-SAFETY VERDICT

## STATUS: 🔴 NOT OPERATIONALLY SAFE
The Identity Domain Separation Refactor is **BUILT** but **NOT OPERATIONALLY SAFE**. While the data schema has been successfully separated into role-specific profiles, several critical regressions in security, performance, and data integrity prevent production readiness.

---

## 1. CRITICAL DISCOVERIES (FAILURES)

### 🚨 [SECURITY] Privilege Escalation via bulk_update/update()
The refactor relies on `User.save()` to block unauthorized role changes (e.g., Citizen -> Super Admin). However, standard Django operations like `User.objects.update(role='super_admin')` and `bulk_update()` completely bypass this check. 
*   **Impact:** Critical vulnerability allowing horizontal and vertical privilege escalation.

### 🛑 [ADMIN] Admin Panel Crash (FieldError)
Searching for users in the Django Admin triggers a `FieldError: Cannot resolve keyword 'full_name' into field`. The refactor converted `full_name` into a property but left it in the `search_fields` of `UserAdmin`.
*   **Impact:** Admin panel is broken for user management/auditing.

### 📉 [PERFORMANCE] OneToOne N+1 Amplification
The compatibility bridges (e.g., `user.department`, `user.full_name`) on the `User` model trigger synchronous OneToOne database lookups for `OfficerProfile`, `CitizenProfile`, and `AdminProfile`. In dashboard list views, this causes an N+1 query explosion.
*   **Impact:** Significant dashboard latency and database pressure under load.

### 🔄 [INTEGRITY] Setter/Getter Inconsistency
The `full_name` property setter on `User` updates the `_legacy_full_name` field, but the getter prioritizes the `OfficerProfile.full_name` field. 
*   **Test Result:** Updating a user's name via `user.full_name = "New Name"` saves successfully to the DB but is **NOT** reflected in the UI because the profile field takes precedence.
*   **Impact:** Profile updates in dashboards are effectively broken.

### 🗺️ [GEOSPATIAL] Stale Denormalized Geo-Fields
The `create_officer_account` service and `OfficerProfile.save()` no longer automatically resolve hierarchy (Village -> Taluka -> District). Officers created via the dashboard may have missing or mismatched district/taluka strings while their `location_id` points elsewhere.
*   **Impact:** Broken geographic filtering and reporting accuracy.

---

## 2. COMPLIANCE AUDIT

| Area | Status | Note |
| :--- | :--- | :--- |
| **Authentication** | ✅ Working | Login/Logout and session persistence remain intact. |
| **Profile Mappings** | ✅ Built | All 1,290 users have correct OneToOne profile links. |
| **Compatibility Bridge** | ⚠️ Unsafe | Functional but triggers N+1 and has setter/getter bugs. |
| **RBAC Isolation** | ⚠️ Leaky | `dept_admin` lacks district-level isolation (State-wide access). |
| **Async Stability** | ⚠️ Fragile | `resolve_hierarchy` in tasks triggers recursive queries. |
| **Transaction Safety** | ❌ Unsafe | Officer metrics (`active_assigned_count`) updated non-atomically. |

---

## 3. PERFORMANCE REGRESSION METRICS

*   **Login Query Count:** 1 -> 3 (Extra lookups for Role-Profile mapping).
*   **Dashboard Query Count (50 Users):** 1 -> 51+ (N+1 via properties).
*   **Assignment Engine:** Non-atomic `count()` based updates on `OfficerProfile` cause "Workload Drift" under concurrency.
*   **Async Tasks:** `resolve_hierarchy` adds ~3 extra queries per task execution.

---

## 4. TECHNICAL DEBT & RISK ANALYSIS

1.  **Workload Drift:** The `update_officer_metrics` signal is prone to race conditions. Concurrent assignments will result in incorrect `fatigue_level` and `active_assigned_count`.
2.  **RBAC Loophole:** The `apply_rbac_filter` for `dept_admin` ignores `jurisdiction_scope`. A district-level department admin can currently view issues for their department across all other districts.
3.  **Migration Rollback:** While renames use `db_column`, the data copied into profiles is not synchronized back to legacy fields. A rollback would result in data loss for any updates made post-migration.

---

## 5. FINAL VERDICT: 🔴 RED (REJECTED)

The refactor achieves the structural goal of domain separation but fails the **operational safety** test. 

### MANDATORY REMEDIATION BEFORE PRODUCTION:
1.  **Fix UserAdmin:** Update `search_fields` to use `_legacy_full_name`.
2.  **Harden RBAC:** Add `update()` and `bulk_update()` prevention to `UserManager` or move escalation checks to `pre_save`.
3.  **Sync Property Setters:** Ensure `User.full_name.setter` also updates the linked profile field if it exists.
4.  **Optimize Dashboard Queries:** Use `select_related('officer', 'citizen_profile', 'admin_profile')` in `AuthenticationMiddleware` or `RBACMiddleware`.
5.  **Fix Signal Atomicity:** Use `F('active_assigned_count') + 1` or `select_for_update()` in `update_officer_metrics`.
6.  **Enforce District Isolation:** Update `apply_rbac_filter` to respect `jurisdiction_scope` for `dept_admin` users.
