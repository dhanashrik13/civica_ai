# IDENTITY MIGRATION AUDIT

## 1. Overview
The goal of this migration is to separate the Authentication core (`User`) from the Governance Domain Data.
Currently, `User` contains overloaded fields like `department`, `full_name`, `phone_no`, `address`, `latitude`, `longitude`, `city`, and `state`. These will be moved to `CitizenProfile`, `OfficerProfile` (existing `Officer` will be refactored to `OfficerProfile` or bridged), and `AdminProfile`.

## 2. Dependency Graph & Foreign Keys to `User` / `Officer`
- **accounts.Officer:** `user = OneToOneField(User)`
- **accounts.CitizenProfile:** `user = OneToOneField(User)` (Already exists but incomplete)
- **issues.Issue:** 
  - `reported_by = ForeignKey(User)`
  - `assigned_by = ForeignKey(User)`
  - `updated_by = ForeignKey(User)`
  - `status_changed_by = ForeignKey(User)`
  - `resolved_by = ForeignKey(User)`
  - `assigned_to = ForeignKey(Officer)`
- **issues.Comment:** `user = ForeignKey(User)`
- **issues.EscalationAppeal:** 
  - `citizen = ForeignKey(User)`
  - `reviewer = ForeignKey(User)`
- **notifications.Notification:** `user = ForeignKey(User)`
- **accounts.AuditLog:** `user = ForeignKey(User)`
- **accounts.AssignmentLog:** `officer = ForeignKey(Officer)`
- **accounts.StaffingPolicy:** `created_by = ForeignKey(User)`
- **dashboards.DashboardWidget:** `user = ForeignKey(User)`

## 3. Unsafe Coupling Areas
- Authentication middleware and RBAC hooks expecting `request.user.department` or `request.user.full_name`.
- Any views/serializers that do `User.objects.create(full_name=...)`
- Async tasks referring to `issue.assigned_to.user.full_name`
- The Django Admin forms for `User` which currently expose `full_name`, `department`, etc.

## 4. Fields to Move
**From User to Profiles:**
- `full_name` -> `CitizenProfile.full_name`, `OfficerProfile.full_name`, `AdminProfile.full_name`
- `phone_no` -> `phone` in profiles
- `address`, `city`, `state`, `latitude`, `longitude` -> Profiles
- `department` -> `AdminProfile.department`, `OfficerProfile.department`

## 5. Fields to Keep in User
- `username`
- `email`
- `password`
- `role`
- `is_active`
- `is_staff`
- `is_superuser`
- `is_approved`
- `last_login`, `date_joined`

## 6. Migration Risks
- **Data Loss:** If we delete columns on `User` before copying data to Profiles.
- **Downtime:** If RBAC checks fail when `request.user.department` is accessed.
- **Admin Brokenness:** If `UserAdmin` isn't updated simultaneously.

## 7. Compatibility Strategy
We will use `@property` on the `User` model to map `full_name`, `phone_no`, `department` to the respective profiles temporarily to ensure zero breakage during the transition.
