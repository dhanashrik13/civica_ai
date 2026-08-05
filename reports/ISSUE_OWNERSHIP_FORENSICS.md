# ISSUE OWNERSHIP FORENSICS

## 1. OWNERSHIP AUDIT
- **Total Issues Analyzed**: 37
- **Ownership Model**: `Issue.reported_by` -> `User`
- **Ownership Correctness**: 100% of analyzed issues are correctly linked to valid `User` records with `role='citizen'`.
- **Mismatches**: 0 issues found with orphaned `reported_by_id` or non-citizen reporters.

## 2. CITIZEN PROFILE SYNC
- **Mechanism**: Counters are currently **static fields** in `CitizenProfile`.
- **Automated Update**: No signals or background tasks are currently implemented to increment `total_reports` on `Issue.save()`.
- **Drift Detection**: Every citizen created during the "population" phase has counts between 1 and 10, regardless of actual issues created.

## 3. EVIDENCE
| Username | Profile Count | Actual Issue Count | Match |
| :--- | :--- | :--- | :--- |
| test_citizen | 0 | 2 | NO |
| citizen_19 | 3 | 0 | NO |
| citizen_01 | 8 | 0 | NO |

**Verdict**: The `Issue` table is the only accurate source of truth. The `CitizenProfile` counters are currently metadata-only and highly inaccurate.
