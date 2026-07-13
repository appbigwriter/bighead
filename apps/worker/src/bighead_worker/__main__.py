from bighead_worker.main import ping_worker


def main() -> None:
    import anyio

    anyio.run(ping_worker)


if __name__ == "__main__":
    main()
