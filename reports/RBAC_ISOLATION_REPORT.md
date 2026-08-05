# RBAC ISOLATION REPORT — Jurisdiction Enforcement

## Isolation Audit: Cross-District Visibility
A critical regression was found where `dept_admin` accounts could occasionally view issues from other districts if those issues were unassigned or if the geographic hierarchy resolution failed.

### Fixes Implemented:
1. **Strict Jurisdiction Filtering:** `apply_rbac_filter` now requires a match on `district`, `taluka`, `village`, `city`, or `ward` against the admin's `jurisdiction_scope`.
2. **Denormalized Geo-Enforcement:** Instead of relying on recursive FK traversal (which is slow and prone to errors), the filter now uses the denormalized geographic fields on the `Issue` model, which are guaranteed to be populated by the `enrich_issue_context` async task and the `LocationService`.
3. **Officer Isolation:** `OfficerProfile` queries are now similarly isolated, preventing a `dept_admin` in Pune from seeing officers in Mumbai.

## Verification Scenarios
| User Role | Jurisdiction | Target District | Access Result |
| :--- | :--- | :--- | :--- |
| Dept Admin | Pune | Pune | **GRANTED** |
| Dept Admin | Pune | Mumbai | **BLOCKED** |
| Dept Admin | (Global) | Any | **GRANTED** (Super Admin only) |
| Officer | N/A | Any | **BLOCKED** (Self-only) |

## Verdict: ISOLATION HARDENED
The "leaky" RBAC implementation has been replaced with a strict geographic and departmental boundary enforcement.
