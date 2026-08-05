# CITIZEN REPORT COUNTER AUDIT

## 1. SUMMARY
- **Total citizens audited:** 581
- **Total issues scanned:** 2
- **Correct counters:** 52
- **Incorrect counters:** 529
- **Drift percentage:** 91.05%

## 2. TOP DRIFT CASES
| Citizen Username | Stored (T/V/R/S) | Actual (T/V/R/S) | Mismatch Amount |
|------------------|------------------|------------------|-----------------|
| pilot_citizen | 4/2/0/2 | 0/0/0/0 | -4 |
| citizen | 9/8/0/1 | 0/0/0/0 | -9 |
| citizen_01 | 8/4/3/1 | 0/0/0/0 | -8 |
| citizen_02 | 4/2/1/1 | 0/0/0/0 | -4 |
| citizen_03 | 2/1/1/0 | 0/0/0/0 | -2 |
| citizen_04 | 5/2/1/2 | 0/0/0/0 | -5 |
| citizen_05 | 8/6/2/0 | 0/0/0/0 | -8 |
| citizen_06 | 7/3/3/1 | 0/0/0/0 | -7 |
| citizen_07 | 4/2/0/2 | 0/0/0/0 | -4 |
| citizen_08 | 1/0/0/1 | 0/0/0/0 | -1 |
| citizen_09@example.com | 6/5/1/0 | 0/0/0/0 | -6 |
| citizen_10 | 8/5/0/3 | 0/0/0/0 | -8 |
| citizen_11 | 8/5/2/1 | 0/0/0/0 | -8 |
| citizen_12 | 10/7/1/2 | 0/0/0/0 | -10 |
| citizen_13 | 2/1/1/0 | 0/0/0/0 | -2 |
| citizen_14 | 7/5/0/2 | 0/0/0/0 | -7 |
| citizen_15 | 8/6/1/1 | 0/0/0/0 | -8 |
| citizen_16 | 9/5/3/1 | 0/0/0/0 | -9 |
| citizen_17 | 5/2/0/3 | 0/0/0/0 | -5 |
| citizen_18 | 5/3/1/1 | 0/0/0/0 | -5 |

## 3. ROOT CAUSE ANALYSIS
Likely causes for detected drift:
1. **Manual Data Population**: The previous task populated CitizenProfile counters with random values that were not linked to actual Issue records.
2. **Schema Evolution**: The `Issue.Status.REJECTED` was removed from the model in earlier migrations, causing stored `rejected_reports` to become orphaned from current statuses.
3. **Decoupled Architecture**: `CitizenProfile` counters are not automatically updated via signals or projections in the current implementation, leading to permanent drift when issues are created or modified.

## 4. SAFETY VERDICT
**CRITICAL DRIFT**
The CitizenProfile counters are currently entirely inaccurate as they were populated with randomized sample data during the "expansion" and "population" phases, rather than being derived from the Issue table. A full synchronization is required to restore integrity.
