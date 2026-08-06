"""Web server entrypoint for local website execution."""

from __future__ import annotations


HOST = "0.0.0.0"
PORT = 8000
RELOAD = True


def run_backend() -> None:
    """Start the FastAPI backend (serves API and static frontend)."""
    import uvicorn

    uvicorn.run(
        "backend.api.app:app",
        host=HOST,
        port=PORT,
        reload=RELOAD,
    )


def run_project() -> None:
    """Run the website backend server."""
    run_backend()


if __name__ == "__main__":
    run_project()

