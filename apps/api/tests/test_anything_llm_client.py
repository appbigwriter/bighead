import httpx
import pytest
import respx
from bighead_pycore.integrations.anythingllm import AnythingLlmClient, AnythingLlmClientError


@pytest.mark.asyncio
@respx.mock
async def test_anything_llm_upload_success():
    client = AnythingLlmClient(api_url="http://localhost:3001", api_key="test-key")

    respx.post("http://localhost:3001/api/v1/document/upload").mock(
        return_value=httpx.Response(
            200,
            json={
                "success": True,
                "documents": [{"location": "custom-documents/test.pdf", "name": "test.pdf"}],
            },
        )
    )

    location = await client.upload_document(b"pdf-content", "test.pdf")
    assert location == "custom-documents/test.pdf"


@pytest.mark.asyncio
@respx.mock
async def test_anything_llm_upload_failure():
    client = AnythingLlmClient(api_url="http://localhost:3001", api_key="test-key")

    respx.post("http://localhost:3001/api/v1/document/upload").mock(
        return_value=httpx.Response(200, json={"success": False})
    )

    with pytest.raises(AnythingLlmClientError) as exc_info:
        await client.upload_document(b"pdf-content", "test.pdf")
    assert "upload returned unsuccessful status" in str(exc_info.value)


@pytest.mark.asyncio
@respx.mock
async def test_anything_llm_update_embeddings_success():
    client = AnythingLlmClient(api_url="http://localhost:3001", api_key="test-key")

    route = respx.post(
        "http://localhost:3001/api/v1/workspace/test-workspace/update-embeddings"
    ).mock(return_value=httpx.Response(200, json={"success": True}))

    await client.update_embeddings(
        workspace_slug="test-workspace", adds=["custom-documents/test.pdf"], deletes=[]
    )
    assert route.called


@pytest.mark.asyncio
@respx.mock
async def test_anything_llm_query_success():
    client = AnythingLlmClient(api_url="http://localhost:3001", api_key="test-key")

    respx.post("http://localhost:3001/api/v1/workspace/test-workspace/chat").mock(
        return_value=httpx.Response(
            200,
            json={
                "text": "De acordo com o manual, o preço é 10.",
                "sources": [{"title": "test.pdf"}],
            },
        )
    )

    result = await client.query_workspace(workspace_slug="test-workspace", query="Qual o preço?")
    assert result["text"] == "De acordo com o manual, o preço é 10."
    assert result["sources"][0]["title"] == "test.pdf"


@pytest.mark.asyncio
@respx.mock
async def test_anything_llm_auth_error():
    client = AnythingLlmClient(api_url="http://localhost:3001", api_key="invalid-key")

    respx.post("http://localhost:3001/api/v1/workspace/test-workspace/chat").mock(
        return_value=httpx.Response(401, text="Unauthorized")
    )

    with pytest.raises(AnythingLlmClientError) as exc_info:
        await client.query_workspace(workspace_slug="test-workspace", query="Olá")
    assert "AnythingLLM query failed" in str(exc_info.value)


@pytest.mark.asyncio
@respx.mock
async def test_anything_llm_timeout_error():
    client = AnythingLlmClient(
        api_url="http://localhost:3001", api_key="test-key", timeout_seconds=0.1
    )

    respx.post("http://localhost:3001/api/v1/workspace/test-workspace/chat").mock(
        side_effect=httpx.TimeoutException("Timeout")
    )

    with pytest.raises(AnythingLlmClientError) as exc_info:
        await client.query_workspace(workspace_slug="test-workspace", query="Olá")
    assert "AnythingLLM query failed" in str(exc_info.value)
