# Authentication Domain Refactor Audit

## Phase 1 & 3: Architectural Changes
* **Centralized User Decoupling:** All authentication-critical fields (`username`, `email`, `password_hash`, `is_active`, `last_login`, `created_at`, `updated_at`) have been moved into `CitizenProfile`, `OfficerProfile`, and `AdminProfile`.
* **DomainIdentityMiddleware:** Successfully implemented to inject `request.citizen`, `request.officer`, and `request.admin` into incoming requests. It reads from a domain-specific session variable (`domain_profile_id`).
* **Authentication Bypass:** Replaced Django's `authenticate` and `login` methods with `authenticate_for_role` and `domain_login` that natively query and verify against the newly added `password_hash` fields in the respective profile models.

## Phase 4: Compatibility State
* **Legacy Support:** The `User` model is still being conditionally instantiated during registration (`register_citizen`) and partially linked in the middleware (`request.user`) strictly to avoid breaking downstream RBAC filters or third-party packages in Phase 4.
* **Views Refactored:** Login, logout, and registration views now operate completely independently of Django's default `AuthenticationMiddleware` session backend.