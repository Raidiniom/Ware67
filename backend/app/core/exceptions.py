from typing import Any


class AppError(Exception):
    """Expected application error that can be safely returned to an API client."""

    def __init__(
        self,
        status_code: int,
        detail: Any,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(str(detail))
        self.status_code = status_code
        self.detail = detail
        self.headers = headers
