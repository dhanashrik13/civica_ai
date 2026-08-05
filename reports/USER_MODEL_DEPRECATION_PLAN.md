# User Model Deprecation Plan (Phase 5)

## Critical Remaining Dependencies
A comprehensive codebase audit reveals that the `User` model remains deeply intertwined with core governance models. **Immediate hard deletion of the `User` model will result in catastrophic foreign key integrity failures.**

### Unrelated Governance Models Still Dependent on `User`:
1. `issues.models.Issue` (`reported_by`, `assigned_to` - wait, `assigned_to` is `OfficerProfile`, but `reported_by` is `User`)
2. `accounts.models.AuditLog` (`user` field)
3. `accounts.models.StaffingPolicy` (`created_by` field)
4. `accounts.models.StaffingRollout` (`approved_by` field)
5. `accounts.models.JurisdictionDispute` (`arbitrator` field)
6. `accounts.models.AdministrativeDirective` (`created_by` field)
7. `notifications.models.Notification` (`user` field)

## Roadmap for Full Deprecation:
1. **Schema Migration:** Create parallel GenericForeignKey or specific ForeignKey fields (e.g., `reported_by_citizen`) on the dependent governance tables.
2. **Data Migration:** Run a background script to map the legacy `user_id` to the respective profile ID in the new relation columns.
3. **Application Logic Rewrite:** Refactor all `Issue` creation, `AuditLog` generation, and Notification queries to use the domain-specific foreign keys.
4. **Drop Legacy Constraints:** Remove the original `User` foreign keys from the database schema.
5. **Drop User Model:** Safely delete the `accounts.User` model and remove it from `settings.AUTH_USER_MODEL`.

**STATUS: PAUSED**
Phase 5 execution is paused pending authorization to modify the governance tables, adhering strictly to the safety mandate "DO NOT touch Issue, Assignment, AuditLog, Event, Projection, Notification, or Governance models."