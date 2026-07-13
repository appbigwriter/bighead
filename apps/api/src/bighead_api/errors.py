from collections.abc import Mapping
from http import HTTPStatus

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from starlette.responses import JSONResponse


def problem_response(
    request: Request,
    status_code: int,
    detail: str,
    *,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    try:
        title = HTTPStatus(status_code).phrase
    except ValueError:
        title = "Request failed"
    payload = {
        "type": "about:blank",
        "title": title,
        "status": status_code,
        "detail": detail,
        "traceId": getattr(request.state, "request_id", ""),
        "instance": request.url.path,
    }
    return JSONResponse(
        payload,
        status_code=status_code,
        headers=headers,
        media_type="application/problem+json",
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, str) else "Request could not be processed"
    return problem_response(request, exc.status_code, detail, headers=exc.headers)


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    fields = sorted({str(error["loc"][-1]) for error in exc.errors() if error.get("loc")})
    detail = "Invalid request" + (f" fields: {', '.join(fields)}" if fields else "")
    return problem_response(request, 422, detail)
