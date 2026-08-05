# PROJECTION SYNC ARCHITECTURE

## 1. AUTOMATED SYNCHRONIZATION
- **Event Triggers**: The synchronization is driven by Django signals (`post_save` and `post_delete` on the `Issue` model).
- **Async Processing**: The signals immediately dispatch the `sync_citizen_profile_counters` task to the Celery outbox, preventing synchronous locking on the hot path.

## 2. PROJECTION SAFETY
- **Idempotency**: The task uses projection rebuild logic. It counts the actual records in the `Issue` table (`Count('id')`) rather than blindly incrementing or decrementing (e.g., via `F()` expressions). This guarantees that even if a task is replayed or executed out of order, the result is mathematically identical to the source of truth.
- **Concurrency Protection**: The task utilizes `transaction.atomic()` and `select_for_update()` to place an exclusive write lock on the `CitizenProfile` row during recalculation, preventing race conditions from concurrent updates.

## 3. ADMIN HARDENING
- The counters in the Django admin are restricted to `readonly_fields`.
- The fieldset has been explicitly labeled **'Civic Trust & Reporting (Derived from Issue table)'** to clearly communicate their projected nature and prevent manual tampering expectations.
