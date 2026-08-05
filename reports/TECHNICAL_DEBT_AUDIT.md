# Technical Debt & Simplification Audit: Civica AI

## 1. DUPLICATED LOGIC
- **Geo-Hierarchy Traversal:** Repeated in `Officer.save` and `enrich_issue_context`. Needs a centralized service.
- **AI Validation:** `CivicAIAssistant` has some residual complexity in `_parse_and_validate_v2`.
- **Signal Chaining:** `handle_issue_notifications` in `issues/signals.py` is quite heavy and relies on `dispatch_task_transactional`.

## 2. OVER-ENGINEERED ABSTRACTIONS
- **ResilienceEngine:** `get_safe` is useful, but the logic for detecting chaos could be simpler.
- **TrustMetricsEngine:** Mathematical-only scores are "Architecture Theater".
- **DriftDetectionEngine:** Currently fragmented across multiple methods.

## 3. SEVERITY & RISK
| Debt ID | Severity | Operational Risk | Maintenance Impact |
| :--- | :--- | :--- | :--- |
| **GEO-DUPE** | MEDIUM | LOW | HIGH (Changes to hierarchy structure require multiple edits) |
| **OUTBOX-DUPE** | MEDIUM | MEDIUM | MEDIUM (Redundant code paths in dispatch) |
| **AI-PARSE-OPAQUE** | LOW | MEDIUM | MEDIUM (Hard to debug LLM parsing errors) |
| **SIGNAL-CHAOS** | HIGH | HIGH | HIGH (Side effects hidden in signals are hard to trace) |

## 4. SIMPLIFICATION STRATEGY
1. **Centralize Geo-Sync:** Create `LocationService.resolve_hierarchy(location)`.
2. **Centralize Health:** Consolidate `TrustMetricsEngine`, `DriftDetectionEngine`, and `OperationalMetric` into a single `OperationalHealthEngine`.
3. **Refactor Issues.save:** Ensure `save()` remains absolutely minimal.
4. **Harden Observability:** Add a `HealthSnapshot` model to store periodic platform-wide metrics.
