import uvicorn


def run() -> None:
    uvicorn.run("local_review_copilot.app:app", host="127.0.0.1", port=8008, reload=True)


if __name__ == "__main__":
    run()

