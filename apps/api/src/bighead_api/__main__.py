import uvicorn

from bighead_api.config import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "bighead_api.main:app",
        host="127.0.0.1",
        port=settings.api_port,
        reload=settings.app_env == "development",
    )


if __name__ == "__main__":
    main()
