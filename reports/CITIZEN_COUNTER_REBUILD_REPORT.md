# CITIZEN COUNTER REBUILD REPORT

## 1. REBUILD SUMMARY
- **Total Citizens Scanned**: 581
- **Citizens Repaired**: 563
- **Total Discrepancies Corrected**: 2751
- **Largest Drift Encountered**: 61

## 2. METHODOLOGY
- All counters (`total_reports`, `valid_reports`, `rejected_reports`, `spam_reports`) were recalculated strictly from the `Issue` table.
- Since `REJECTED` and `SPAM` statuses were removed from the `Issue` model, these counters have been safely zeroed out for all citizens.
- `last_reported_at` was synced to the most recent issue creation date.
