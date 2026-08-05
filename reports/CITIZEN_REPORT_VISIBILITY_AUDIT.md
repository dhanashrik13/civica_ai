# CITIZEN REPORT VISIBILITY AUDIT

## 1. INCIDENT DESCRIPTION
Citizens report a discrepancy where the `CitizenProfile` shows a positive `total_reports` count (e.g., 3), but the dashboard (/citizen/reports/) shows "No reports available".

## 2. AUDIT FINDINGS
- **Test Citizen Trace**: `citizen_19` has `total_reports: 3` stored in `CitizenProfile`.
- **Database Verification**: `Issue.objects.filter(reported_by__username='citizen_19')` returns **0 rows**.
- **Counter Origin**: Findings from `CITIZEN_REPORT_COUNTER_AUDIT.md` confirm that `CitizenProfile` counters were populated with **randomized sample data** during a previous population phase.
- **Linkage Integrity**: Issues are correctly linked to `User` objects via `reported_by` FK, but the counts stored in `CitizenProfile` were never synchronized with the `Issue` table.

## 3. IMPACT ANALYSIS
- **User Confusion**: Citizens see incorrect stats that do not match their actual activity.
- **Trust Erosion**: The "System Reality" is perceived as broken when counters drift from actual data.

## 4. FINAL VERDICT
**ROOT CAUSE: PROFILE/USER DESYNC**
The issue is NOT a query bug or a permission failure; it is a data integrity failure where the profile counters are stale/random and do not reflect the source-of-truth `Issue` table.
