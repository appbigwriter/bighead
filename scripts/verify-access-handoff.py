"""Validate the Sprint 2 access handoff against the canonical OpenAPI snapshot."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
OPENAPI = ROOT / "packages" / "contracts" / "openapi" / "openapi.yaml"
HANDOFF = ROOT / "docs" / "frontend-backend" / "acesso-organizacoes.md"

document = yaml.safe_load(OPENAPI.read_text(encoding="utf-8"))
handoff = HANDOFF.read_text(encoding="utf-8")
schemas = document["components"]["schemas"]
paths = document["paths"]

expected_schema_properties = {
    "LoginRequest": {"email", "passwordOrMagicLink", "provider"},
    "AuthSessionResponse": {"session", "user", "memberships", "status"},
    "RecoveryRequestedResponse": {"status", "expiresAt"},
    "InvitationAcceptRequest": {"fullName", "password", "accept"},
    "InvitationAcceptResponse": {"membership", "nextRoute"},
    "OnboardingSubmitRequest": {"profile", "organization", "goals", "approvalPolicy"},
    "OnboardingSubmitResponse": {"organizationId", "ownerMembershipId", "nextRoute"},
    "OrganizationListResponse": {"organizations", "currentOrganizationId"},
    "SwitchOrganizationResponse": {"organizationId", "role", "status"},
    "GlobalSearchRequest": {"query", "scopes", "limit"},
    "GlobalSearchResponse": {"groups", "shortcuts", "removedCount"},
    "NotificationListResponse": {"items", "unreadCount", "nextCursor"},
    "PreferencesPatchRequest": {
        "theme",
        "locale",
        "timezone",
        "accessibility",
        "expectedUpdatedAt",
    },
    "PreferencesResponse": {"profile", "preferences", "sessions"},
    "SessionRevokeRequest": {"scope"},
    "AnalyticsSummaryResponse": {
        "cards",
        "drilldowns",
        "alerts",
        "source",
        "period",
        "timezone",
        "freshness",
        "calculatedAt",
        "filters",
        "reconciliation",
    },
}

for schema_name, expected in expected_schema_properties.items():
    actual = set(schemas[schema_name].get("properties", {}))
    if actual != expected:
        raise AssertionError(
            f"{schema_name}: documented contract expects {sorted(expected)}, "
            f"OpenAPI has {sorted(actual)}"
        )
    missing_in_handoff = [
        property_name for property_name in expected if property_name not in handoff
    ]
    if missing_in_handoff:
        raise AssertionError(f"{schema_name}: handoff omits {missing_in_handoff}")

expected_operations = {
    ("/v1/auth/login", "post", "200"),
    ("/v1/auth/recovery", "post", "202"),
    ("/v1/invitations/{token}/accept", "post", "200"),
    ("/v1/onboarding", "post", "201"),
    ("/v1/organizations", "get", "200"),
    ("/v1/organizations/{organization_id}/switch", "post", "200"),
    ("/v1/analytics/summary", "get", "200"),
    ("/v1/search/global", "post", "200"),
    ("/v1/notifications", "get", "200"),
    ("/v1/preferences", "get", "200"),
    ("/v1/preferences", "patch", "200"),
    ("/v1/sessions/revoke", "post", "204"),
}

for path, method, response_status in expected_operations:
    operation = paths.get(path, {}).get(method)
    if not operation:
        raise AssertionError(f"OpenAPI is missing {method.upper()} {path}")
    if response_status not in operation.get("responses", {}):
        raise AssertionError(f"{method.upper()} {path} is missing response {response_status}")

print("Sprint 2 access handoff verified against canonical OpenAPI schemas and statuses.")
