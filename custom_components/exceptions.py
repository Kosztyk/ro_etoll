"""Errors exposed to Home Assistant without response bodies or credentials."""

from homeassistant.exceptions import HomeAssistantError


class RoEtollError(HomeAssistantError):
    """Base integration error."""


class RoEtollAuthError(RoEtollError):
    """The portal rejected the account credentials or refresh token."""


class RoEtollConnectionError(RoEtollError):
    """The portal could not be reached."""


class RoEtollApiError(RoEtollError):
    """Unexpected status or response schema."""

    def __init__(self, message: str, *, http_status: int | None = None) -> None:
        super().__init__(message)
        self.http_status = http_status


class RoEtollAuthUnsupported(RoEtollAuthError):
    """The account/client requires interactive authentication."""


class RoEtollProfileError(RoEtollApiError):
    """No unambiguous current portal profile is available."""
