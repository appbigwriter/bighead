from uuid import UUID

import pytest
from bighead_api.crm_integrations import (
    CrmConnectionCreate,
    _sanitize_configuration,
    _secret_reference,
)
from pydantic import ValidationError


def test_connection_accepts_only_secret_reference_and_safe_configuration() -> None:
    payload = CrmConnectionCreate(
        providerKey="hubspot",
        displayName="Tenant CRM",
        configuration={"pipeline": "sales"},
    )
    assert payload.provider_key == "hubspot"
    assert "secretRef" not in payload.model_dump(by_alias=True)


@pytest.mark.parametrize(
    "configuration",
    [
        {"apiKey": "leak"},
        {"nested": {"access_token": "leak"}},
        {"providerUrl": "https://attacker.example"},
    ],
)
def test_connection_rejects_secret_like_or_endpoint_configuration(configuration) -> None:
    with pytest.raises(ValidationError):
        CrmConnectionCreate(
            providerKey="hubspot",
            displayName="Unsafe",
            configuration=configuration,
        )


def test_legacy_response_configuration_is_recursively_redacted() -> None:
    assert _sanitize_configuration(
        {"nested": {"client_secret": "x"}, "items": [{"access_token": "y"}]}
    ) == {
        "nested": {"client_secret": "[REDACTED]"},
        "items": [{"access_token": "[REDACTED]"}],
    }


def test_provider_secret_reference_is_collision_resistant() -> None:
    organization = UUID("10000000-0000-0000-0000-000000000001")
    assert _secret_reference(organization, "foo-bar") != _secret_reference(organization, "foo_bar")
