# STRICT IDENTITY DOMAIN INTEGRITY AUDIT - FINAL REPORT

**Date:** 2026-05-13  
**Status:** COMPLETE  
**Verdict:** 🚨 **DOMAIN LEAKAGE DETECTED**

## 1. ROLE ↔ PROFILE INTEGRITY SUMMARY

*   **Total Users Audited:** 1296
*   **Total Issues Detected:** 4
*   **Affected Accounts:**
    *   `load_admin` (Role: `super_admin`)
    *   `load_officer` (Role: `officer`)

### Detailed Mappings:

| Username | Role | Profiles Found | Integrity Issue |
| :--- | :--- | :--- | :--- |
| `load_admin` | `super_admin` | `CitizenProfile` | **Domain Leakage** (Illegal Profile) |
| `load_admin` | `super_admin` | *None* | **Missing Required Profile** (`AdminProfile`) |
| `load_officer` | `officer` | `CitizenProfile`, `OfficerProfile` | **Multiple Profiles Attached** |
| `load_officer` | `officer` | `CitizenProfile` | **Domain Leakage** (Illegal Profile) |

---

## 2. MIGRATION & SIGNAL FORENSICS

### Root Causes:

1.  **Faulty Load-Test Logic (`real_load_test.py`):**
    *   `User.objects.get_or_create(username="load_officer", ...)` is called without a role.
    *   `UserManager.create_user` defaults the role to `citizen`.
    *   The `post_save` signal `create_citizen_profile` fires immediately.
    *   The script then updates the role to `officer` and saves with `skip_clean=True`.
    *   This results in an `officer` user keeping an illegal `CitizenProfile`.

2.  **Incomplete Admin Migration:**
    *   Migration `0035` introduced `AdminProfile` but did not include a data migration to populate it for existing users.
    *   While `data_migration.py` was created to address this, it does not include logic to **delete** invalid/illegal profiles, leaving the "leaked" profiles in the database.

3.  **Signal Limitations:**
    *   `create_admin_profile` signal only triggers on `created=True`. When `load_admin` is updated from `citizen` to `super_admin` in the load test, the signal does NOT fire, resulting in a missing `AdminProfile`.

---

## 3. ADMIN PANEL SAFETY VALIDATION

*   **Status:** **FAIL**
*   **Findings:**
    *   `CitizenProfileAdmin`, `OfficerAdmin`, and `AdminProfileAdmin` do not implement `get_queryset` filtering.
    *   Illegal profile mappings (like `load_officer` having both) will appear in both admin sections.
    *   Foreign Key selection in the admin UI does not restrict users by their assigned role.

---

## 4. RBAC SAFETY VALIDATION

*   **Status:** **UNSAFE**
*   **Findings:**
    *   **Direct Access Risk:** Multiple views access profiles directly (e.g., `user.officer`, `user.admin_profile`) without `hasattr` checks or role verification.
    *   **Logic Errors Detected:** In `dashboards/views.py`, the `officer_dashboard` incorrectly attempts to access `request.user.admin_profile.department`. This will cause a `RelatedObjectDoesNotExist` exception for any valid Officer who (correctly) lacks an `AdminProfile`.
    *   **Implicit Trust:** Several templates and services assume that the existence of a profile bridge implies the user holds that role, which is false given the current data corruption.

---

## 5. FINAL VERDICT & CLASSIFICATION

### **VERDICT: DOMAIN LEAKAGE DETECTED**

The identity system is currently **partially corrupted**. While the core RBAC checks (`user.role`) remain functional for most permissions, the "Profile Layer" has leaked across domains. This creates a significant surface area for:
1.  **System Crashes:** Due to missing required profiles for specific roles.
2.  **Data Confusion:** Where a single user appears in multiple domain contexts (Citizen vs. Officer).
3.  **Potential Escalation:** If any logic branch trusts the profile existence over the role field.

### **REMEDIATION REQUIRED:**

1.  **Database Cleanup:** Execute a script to delete all `CitizenProfile` entries where `user.role != 'citizen'`.
2.  **Profile Synthesis:** Ensure all `DEPT_ADMIN` and `SUPER_ADMIN` users have an `AdminProfile`.
3.  **Code Correction:** Fix `dashboards/views.py:209` to use `user.officer.department` instead of `admin_profile`.
4.  **Admin Hardening:** Add queryset filtering to Admin classes in `accounts/admin.py`.
5.  **Load Test Fix:** Update `real_load_test.py` to specify the `role` during `get_or_create`.

---
*Audit performed by Gemini CLI.*
