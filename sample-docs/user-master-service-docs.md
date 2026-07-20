# User Master Service — API Reference

**Version:** 2.4.0 | **Team:** Platform Engineering — Identity & Access | **Updated:** July 2026

---

## 1. Service Overview

The User Master Service (UMS) is the single source of truth for all identity and access management within the platform. It owns the lifecycle of users, groups, roles, and permissions across all downstream services.

**Base URL (production):** `https://api.internal.acme.com/ums/v2`  
**Base URL (staging):** `https://api-staging.internal.acme.com/ums/v2`

### Capabilities

- User lifecycle management (create, read, update, deactivate, delete)
- Group management with hierarchical nesting (up to 5 levels)
- Role-based access control (RBAC) with fine-grained action permissions
- Password policy enforcement and self-service password reset
- Email verification and MFA enrollment
- Audit logging for all mutating operations
- SCIM 2.0 provisioning endpoint for IdP sync
- Rate limiting and brute-force protection

### Authentication

All endpoints require a bearer token issued by the platform's OAuth 2.0 authorization server.

```
Authorization: Bearer <access_token>
Content-Type: application/json
X-Request-ID: <uuid>
```

Service-to-service calls must use a machine client token with the `ums:admin` scope.

### Rate Limits

| Endpoint Group | Authenticated limit | Unauthenticated limit | Burst |
|---|---|---|---|
| User read (GET) | 1 000 req / min | 100 req / min | 2 000 req / 10 s |
| User write (POST/PATCH) | 200 req / min | N/A | 500 req / 10 s |
| Auth / password reset | 10 req / min / IP | 5 req / min / IP | 20 req / 10 s |
| Bulk operations | 10 req / min | N/A | N/A |

---

## 2. Data Models

### 2.1 User Object

```json
{
  "id":               "usr_01J4K8XMAB3CZQD9YFGHP2N7V",
  "username":         "jane.doe",
  "email":            "jane.doe@acme.com",
  "email_verified":   true,
  "first_name":       "Jane",
  "last_name":        "Doe",
  "display_name":     "Jane Doe",
  "phone":            "+1-415-555-0100",
  "phone_verified":   false,
  "status":           "active",
  "locale":           "en-US",
  "timezone":         "America/Los_Angeles",
  "metadata":         { "department": "Engineering", "employee_id": "E1042" },
  "roles":            ["role_viewer", "role_engineer"],
  "groups":           ["grp_platform_eng", "grp_on_call"],
  "mfa_enabled":      true,
  "mfa_methods":      ["totp", "sms"],
  "password_changed_at": "2026-03-01T12:00:00Z",
  "last_login_at":    "2026-07-18T09:34:12Z",
  "failed_login_attempts": 0,
  "locked_until":     null,
  "created_at":       "2024-11-15T08:00:00Z",
  "updated_at":       "2026-07-01T10:22:33Z",
  "created_by":       "usr_admin_01"
}
```

### User Status Values

| Status | Description | Can Login? |
|---|---|---|
| `pending_verification` | Account created, email not verified | No |
| `active` | Fully provisioned and able to log in | Yes |
| `suspended` | Temporarily blocked by admin or policy | No |
| `deactivated` | Soft-deleted; data retained 90 days | No |
| `deleted` | Hard-deleted; PII purged asynchronously | No |
| `locked` | Too many failed login attempts | No |

### 2.2 Group Object

```json
{
  "id":           "grp_01J9PLATFORM_ENG",
  "name":         "platform-engineering",
  "display_name": "Platform Engineering",
  "description":  "Core platform infra team",
  "parent_id":    "grp_01J9ENGINEERING",
  "depth":        2,
  "member_count": 18,
  "roles":        ["role_infra_admin", "role_deploy"],
  "metadata":     { "cost_center": "CC-102" },
  "created_at":   "2024-01-10T00:00:00Z"
}
```

### 2.3 Role & Permission Objects

```json
{
  "id":          "role_engineer",
  "name":        "engineer",
  "display_name":"Engineer",
  "permissions": ["action:repo:read", "action:ci:trigger", "action:deploy:staging", "action:secret:read"],
  "is_system":   false
}
```

Permission format: `action:<resource>:<operation>`

---

## 3. User Management

### 3.1 Create User

**POST** `/users`

Creates a new user account with the strictest validation rules.

#### Required Scopes

| Scope | Description |
|---|---|
| `ums:user:create` | Creates user in caller's tenant |
| `ums:admin` | Creates user in any tenant; platform service accounts only |

#### Request Fields

| Field | Type | Required | Description |
|---|---|---|---|
| `username` | string | Yes | Unique login handle. 3–64 chars. |
| `email` | string | Yes | Primary email. Must be globally unique. |
| `password` | string | Conditional | Required if `send_invite` is false. |
| `first_name` | string | Yes | 1–80 characters. Unicode allowed. |
| `last_name` | string | Yes | 1–80 characters. Unicode allowed. |
| `phone` | string | No | E.164 format, e.g. +14155550100. |
| `locale` | string | No | BCP-47 tag. Defaults to tenant locale. |
| `timezone` | string | No | IANA timezone. Defaults to UTC. |
| `roles` | string[] | No | Role IDs to assign on creation. |
| `groups` | string[] | No | Group IDs to add user to. |
| `metadata` | object | No | Arbitrary key-value pairs. Max 50 keys, 1 KB total. |
| `send_invite` | boolean | No | Default true. Sends verification email. |
| `force_mfa` | boolean | No | Default false. Requires MFA on first login. |
| `expire_password` | boolean | No | Forces password change on first login. |

#### Username Validation Rules

| Rule | Constraint |
|---|---|
| Length | 3 – 64 characters |
| Allowed characters | a–z, 0–9, underscore (_), hyphen (-), dot (.) |
| Must start with | Letter or digit |
| Must not end with | . or - |
| Consecutive specials | Not allowed (e.g. "jane..doe" is invalid) |
| Case handling | Stored as-is, compared case-insensitively |
| Reserved names | admin, root, system, api, ums, null, undefined, anonymous |
| Uniqueness | Globally unique within tenant |

#### Email Validation Rules

| Rule | Constraint |
|---|---|
| Format | RFC 5322 compliant |
| Domain MX record | Domain must have resolvable MX records |
| Disposable email | Domains on blocklist rejected (e.g. mailinator.com) |
| Plus addressing | Allowed. jane+work@acme.com is valid. |
| Case | Local part stored as-is; domain lowercased |
| Uniqueness | Globally unique across all tenants |
| Maximum length | 254 characters |

#### Password Policy (Platform Defaults)

| Rule | Requirement |
|---|---|
| Minimum length | 12 characters |
| Maximum length | 128 characters |
| Uppercase letters | At least 1 required |
| Lowercase letters | At least 1 required |
| Digits | At least 1 required |
| Special characters | At least 1 of: `! @ # $ % ^ & * ( ) - _ = + [ ] { }` |
| No whitespace | Leading/trailing whitespace rejected |
| No username in password | Case-insensitive check |
| Breach check | Checked against HaveIBeenPwned (k-anonymity model) |
| Reuse prevention | Cannot reuse last 12 passwords |
| Expiry | 90 days (configurable 30–365 days) |
| Common passwords | Top 10 000 common passwords rejected |

#### Example Request — Self-Registration

```json
POST /ums/v2/users
Authorization: Bearer eyJhbGci...
Content-Type: application/json

{
  "username":    "jane.doe",
  "email":       "jane.doe@acme.com",
  "first_name":  "Jane",
  "last_name":   "Doe",
  "phone":       "+14155550100",
  "locale":      "en-US",
  "timezone":    "America/Los_Angeles",
  "roles":       ["role_viewer"],
  "groups":      ["grp_new_employees"],
  "metadata":    { "department": "Engineering", "employee_id": "E1042" },
  "send_invite": true,
  "force_mfa":   false
}
```

#### Success Response — 201 Created

```json
{
  "id":             "usr_01J4K8XMAB3CZQD9YFGHP2N7V",
  "username":       "jane.doe",
  "email":          "jane.doe@acme.com",
  "email_verified": false,
  "status":         "pending_verification",
  "created_at":     "2026-07-19T10:00:00Z",
  "invite_sent":    true
}
```

#### Error Responses for Create User

| HTTP Status | Error Code | Description |
|---|---|---|
| 400 | `VALIDATION_ERROR` | One or more fields failed validation |
| 400 | `WEAK_PASSWORD` | Password does not meet policy |
| 400 | `BREACHED_PASSWORD` | Password found in breach database |
| 400 | `DISPOSABLE_EMAIL` | Email domain not allowed |
| 409 | `USERNAME_TAKEN` | Username already exists in tenant |
| 409 | `EMAIL_TAKEN` | Email already registered globally |
| 403 | `INSUFFICIENT_SCOPE` | Token lacks `ums:user:create` scope |
| 422 | `INVALID_ROLE` | One or more role IDs do not exist |
| 422 | `INVALID_GROUP` | One or more group IDs do not exist |

### 3.2 Get User

**GET** `/users/{user_id}`

Returns the full User Object. Supports field projection via `?fields=id,email,status` and sideloading via `?include=roles,groups,permissions`.

### 3.3 List Users

**GET** `/users`

| Parameter | Default | Description |
|---|---|---|
| `page` | 1 | Page number |
| `per_page` | 20 | Max 100 |
| `status` | — | Filter by status |
| `role` | — | Filter by role ID |
| `group` | — | Filter by group ID (includes nested members) |
| `q` | — | Full-text search on name, email, username |
| `sort` | `created_at` | Sort field |
| `order` | `desc` | `asc` or `desc` |
| `created_after` | — | ISO8601 datetime filter |
| `created_before` | — | ISO8601 datetime filter |

### 3.4 Update User

**PATCH** `/users/{user_id}`

Partial update. Changing email triggers re-verification. Changing username is blocked if the user has active sessions.

### 3.5 Deactivate / Delete User

| Method | Endpoint | Effect |
|---|---|---|
| POST | `/users/{user_id}/deactivate` | Sets status to `deactivated`. Revokes all tokens. Data retained. |
| POST | `/users/{user_id}/suspend` | Sets status to `suspended`. Reversible. |
| DELETE | `/users/{user_id}` | Schedules hard delete. PII purged within 24 hours. Irreversible. |

### 3.6 Password Management

| Endpoint | Description |
|---|---|
| POST `/users/{user_id}/password` | Admin-initiated password reset |
| POST `/auth/password-reset/request` | Sends reset email. Public, rate-limited. |
| POST `/auth/password-reset/confirm` | Validates token and sets new password |
| POST `/users/{user_id}/unlock` | Manually unlocks a locked account |
| GET `/users/{user_id}/password-policy` | Returns effective password policy |

---

## 4. Group Management

Groups provide hierarchical organization of users. Max depth is 5 levels. Permissions flow down the hierarchy — users inherit all roles from ancestor groups.

### Group Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/groups` | Create a new group |
| GET | `/groups` | List all groups |
| GET | `/groups/{group_id}` | Get group details |
| PATCH | `/groups/{group_id}` | Update group |
| DELETE | `/groups/{group_id}` | Delete group (must be empty) |
| POST | `/groups/{group_id}/members` | Add user(s) to group |
| DELETE | `/groups/{group_id}/members/{user_id}` | Remove user from group |
| POST | `/groups/{group_id}/roles` | Assign role(s) to group |
| GET | `/groups/{group_id}/effective-permissions` | Resolved permission set |

### Hierarchy Rules

- Maximum nesting depth: 5 levels
- A group cannot be its own ancestor (cycle detection enforced)
- Deleting a parent group is blocked if it has child groups
- Effective roles = direct roles ∪ all ancestor group roles
- Moving a group re-evaluates all member effective permissions

---

## 5. Roles & Permissions (RBAC)

Roles contain permissions (actions). Users and groups are assigned roles. A user's effective permission set is the union of all permissions from all direct and inherited roles.

### Built-in System Roles

| Role ID | Display Name | Description |
|---|---|---|
| `role_super_admin` | Super Admin | Full platform access. Cannot be custom-assigned. |
| `role_admin` | Admin | Full UMS access within tenant |
| `role_user_manager` | User Manager | Create/update/deactivate users. Cannot change roles. |
| `role_engineer` | Engineer | Repos, CI, staging deploys, secret read |
| `role_viewer` | Viewer | Read-only access to all non-sensitive resources |
| `role_billing` | Billing Admin | Billing and invoices only |
| `role_auditor` | Auditor | Audit logs and compliance reports |

### Permission Format

Format: `action:<resource>:<operation>`

| Permission | Description |
|---|---|
| `action:user:read` | View user profiles and metadata |
| `action:user:create` | Create new user accounts |
| `action:user:update` | Modify user profiles |
| `action:user:delete` | Delete user accounts |
| `action:group:manage` | Create, update, delete groups |
| `action:role:assign` | Assign roles to users/groups |
| `action:repo:read` | Clone and read repositories |
| `action:repo:write` | Push to repositories |
| `action:ci:trigger` | Trigger CI pipeline runs |
| `action:deploy:staging` | Deploy to staging environment |
| `action:deploy:production` | Deploy to production environment |
| `action:secret:read` | Read secrets from vault |
| `action:secret:write` | Create/update secrets |
| `action:audit:read` | Access audit logs |
| `action:billing:manage` | Manage billing and invoices |

### Effective Permissions Check

```
GET /ums/v2/users/{user_id}/effective-permissions
```

Returns the resolved union of all permissions with source attribution (which role/group granted each permission).

---

## 6. Audit Log

Every mutating operation writes an immutable audit event. Retained for 2 years.

### Audited Event Types

| Event Type | Trigger |
|---|---|
| `user.created` | New user account created |
| `user.updated` | Any user field changed |
| `user.deactivated` | User deactivated or suspended |
| `user.deleted` | User hard-deleted |
| `user.locked` | Account locked after failed attempts |
| `user.unlocked` | Account unlocked |
| `user.login_failed` | Failed login attempt |
| `user.login_success` | Successful login |
| `user.password_changed` | Password changed by user or admin |
| `user.mfa_enrolled` | MFA method added |
| `role.assigned` | Role assigned to user or group |
| `group.member_added` | User added to group |

---

## 7. Error Reference

All errors follow:

```json
{
  "error":      "ERROR_CODE",
  "message":    "Human-readable description",
  "errors":     [],
  "request_id": "<uuid>",
  "docs_url":   "https://docs.acme.com/ums/errors#ERROR_CODE"
}
```

| HTTP | Error Code | Resolution |
|---|---|---|
| 400 | `VALIDATION_ERROR` | See errors[] for field-level details |
| 400 | `WEAK_PASSWORD` | Check password policy endpoint |
| 400 | `BREACHED_PASSWORD` | Choose a different password |
| 400 | `DISPOSABLE_EMAIL` | Use a permanent email address |
| 400 | `INVALID_TOKEN` | Token expired or already used |
| 401 | `UNAUTHENTICATED` | Re-authenticate |
| 403 | `INSUFFICIENT_SCOPE` | Token lacks required scope |
| 403 | `FORBIDDEN` | No permission for this resource |
| 404 | `USER_NOT_FOUND` | No user with that ID in this tenant |
| 404 | `GROUP_NOT_FOUND` | No group with that ID |
| 409 | `USERNAME_TAKEN` | Choose a different username |
| 409 | `EMAIL_TAKEN` | Use password reset if this is your account |
| 409 | `GROUP_NOT_EMPTY` | Remove all members before deleting group |
| 422 | `CIRCULAR_GROUP` | Would create a cycle in the group hierarchy |
| 422 | `MAX_DEPTH_EXCEEDED` | Nesting exceeds maximum depth of 5 |
| 429 | `RATE_LIMITED` | Check Retry-After header |
| 500 | `INTERNAL_ERROR` | Retry with exponential backoff |

---

## 8. Changelog

| Version | Date | Change |
|---|---|---|
| 2.4.0 | Jul 2026 | Added `force_mfa` on user creation. Added permission source attribution in effective-permissions. |
| 2.3.0 | Apr 2026 | Breach check now runs synchronously on creation. |
| 2.2.0 | Jan 2026 | Group hierarchy depth increased to 5. Circular detection added. |
| 2.1.0 | Sep 2025 | Added `expire_password`. Audit log retention increased to 2 years. |
| 2.0.0 | Jan 2025 | BREAKING: User IDs migrated to ULID format (usr_ prefix). |
| 1.8.0 | Jun 2024 | Added SCIM 2.0. Added metadata field on User and Group. |
