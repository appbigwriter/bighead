import pytest
from bighead_worker.jobs import heartbeat_job


class SettingsStub:
    queue_name = "bighead:jobs"


@pytest.mark.asyncio
async def test_heartbeat_job_returns_expected_payload() -> None:
    result = await heartbeat_job({"settings": SettingsStub()})
    assert result.status == "ok"
    assert result.queue_name == "bighead:jobs"
