"""Read eToll data using the public portal's OIDC client and API contract.

The session is owned by Home Assistant. Tokens stay in this instance; shared
headers/cookies are never changed. The only data POST is the read-only toll
verification operation, not a purchase or vehicle-validation operation.
"""

from __future__ import annotations

import asyncio
import math
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urlsplit

import aiohttp

from .const import BASE_URL, CLIENT_ID, MAX_PAGES, PAGE_SIZE, REQUEST_TIMEOUT, TOKEN_URL
from .exceptions import (
    RoEtollApiError,
    RoEtollAuthError,
    RoEtollAuthUnsupported,
    RoEtollConnectionError,
    RoEtollProfileError,
)


class RoEtollAPI:
    """Account-scoped client for the eToll portal."""

    def __init__(
        self, session: aiohttp.ClientSession, username: str, password: str
    ) -> None:
        self._session = session
        self._username = username.strip()
        self._password = password
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._expires_at = 0.0
        self._retry_at = 0.0
        self._auth_lock = asyncio.Lock()

    @property
    def authenticated(self) -> bool:
        return bool(self._access_token) and time.monotonic() < self._expires_at

    def _check_backoff(self) -> None:
        if time.monotonic() < self._retry_at:
            raise RoEtollConnectionError("eToll rate limit: waiting for Retry-After.")

    async def _json_request(self, method: str, url: str, **kwargs: Any) -> Any:
        self._check_backoff()
        try:
            async with self._session.request(
                method,
                url,
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
                allow_redirects=False,
                **kwargs,
            ) as response:
                status = response.status
                if status == 429:
                    value = response.headers.get("Retry-After", "300")
                    try:
                        delay = float(value)
                    except ValueError:
                        try:
                            delay = (
                                parsedate_to_datetime(value).timestamp() - time.time()
                            )
                        except (ValueError, TypeError, OverflowError):
                            delay = 300
                    self._retry_at = time.monotonic() + (
                        max(1, delay) if math.isfinite(delay) else 300
                    )
                    raise RoEtollConnectionError("eToll rate limit (HTTP 429).")
                if status >= 500:
                    raise RoEtollConnectionError(
                        f"eToll temporarily unavailable (HTTP {status})."
                    )
                if url != TOKEN_URL and status == 401:
                    raise RoEtollAuthError("eToll access token rejected (HTTP 401).")
                # Token errors are JSON; never include error_description or body in logs.
                if url != TOKEN_URL and status != 200:
                    raise RoEtollApiError(
                        f"eToll {method} {urlsplit(url).path} returned HTTP {status}.",
                        http_status=status,
                    )
                try:
                    data = await response.json(content_type=None)
                except (ValueError, aiohttp.ContentTypeError) as err:
                    raise RoEtollApiError("eToll returned invalid JSON.") from err
                if url == TOKEN_URL and status != 200:
                    code = data.get("error") if isinstance(data, dict) else None
                    if code in {
                        "unauthorized_client",
                        "invalid_client",
                        "unsupported_grant_type",
                    }:
                        raise RoEtollAuthUnsupported(
                            "eToll does not allow password login for this client."
                        )
                    if code in {"invalid_grant", "access_denied"} or status == 401:
                        raise RoEtollAuthError(
                            "eToll rejected the credentials. Check the account in the portal."
                        )
                    raise RoEtollApiError(
                        f"eToll authentication service returned HTTP {status}."
                    )
                if not isinstance(data, (dict, list)):
                    raise RoEtollApiError("eToll returned an unexpected JSON value.")
                return data
        except (aiohttp.ClientError, TimeoutError) as err:
            raise RoEtollConnectionError("Cannot connect to eToll.") from err

    async def _token_request(self, payload: dict) -> None:
        data = await self._json_request(
            "POST", TOKEN_URL, data={"client_id": CLIENT_ID, **payload}
        )
        if (
            not isinstance(data, dict)
            or not isinstance(data.get("access_token"), str)
            or not data["access_token"]
        ):
            raise RoEtollApiError("eToll did not return an access token.")
        try:
            expires_in = float(data["expires_in"])
        except (KeyError, ValueError, TypeError) as err:
            raise RoEtollApiError("eToll returned an invalid token lifetime.") from err
        if not math.isfinite(expires_in) or expires_in <= 0:
            raise RoEtollApiError("eToll returned an invalid token lifetime.")
        token_type = data.get("token_type", "Bearer")
        if not isinstance(token_type, str) or token_type.lower() != "bearer":
            raise RoEtollApiError("eToll returned an unsupported token type.")
        self._access_token = data["access_token"]
        refresh = data.get("refresh_token")
        self._refresh_token = refresh if isinstance(refresh, str) and refresh else None
        self._expires_at = time.monotonic() + expires_in - min(30, expires_in / 10)

    async def authenticate(self, *, rejected_token: str | None = None) -> None:
        """Refresh tokens first; retry with the account password after expiry."""
        async with self._auth_lock:
            if self.authenticated and (
                rejected_token is None or self._access_token != rejected_token
            ):
                return
            self._access_token = None
            self._expires_at = 0
            if self._refresh_token:
                try:
                    await self._token_request(
                        {
                            "grant_type": "refresh_token",
                            "refresh_token": self._refresh_token,
                        }
                    )
                    return
                except RoEtollAuthUnsupported:
                    raise
                except RoEtollAuthError:
                    self._refresh_token = None
            await self._token_request(
                {
                    "grant_type": "password",
                    "username": self._username,
                    "password": self._password,
                    "scope": "openid profile",
                }
            )

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        allowed = {
            ("GET", "/api/profiles"),
            ("GET", "/api/vehicles"),
            ("GET", "/api/invoices"),
            ("GET", "/api/resources/countries"),
            ("POST", "/api/tolls/verification"),
        }
        if (method, path) not in allowed:
            raise RoEtollApiError(
                "This operation is not a supported monitoring request."
            )
        await self.authenticate()
        for attempt in range(2):
            token = self._access_token
            try:
                return await self._json_request(
                    method,
                    BASE_URL + path,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/json",
                    },
                    **kwargs,
                )
            except RoEtollAuthError:
                if attempt:
                    raise
                await self.authenticate(rejected_token=token)
        raise RoEtollAuthError("eToll authentication failed.")

    @staticmethod
    def _items(data: Any, key: str) -> list[dict]:
        if isinstance(data, dict):
            # ProfileListResult uses a capitalized property in the official client.
            data = data.get(key, data.get(key[0].upper() + key[1:]))
        if not isinstance(data, list) or any(
            not isinstance(item, dict) for item in data
        ):
            raise RoEtollApiError(f"eToll returned an unexpected {key} response.")
        return data

    async def _collection(
        self, path: str, key: str, params: dict | None = None
    ) -> list[dict]:
        params = dict(params or {})
        seen: set[str] = set()
        result: list[dict] = []
        for _ in range(MAX_PAGES):
            data = await self._request("GET", path, params=params)
            result.extend(self._items(data, key))
            cursor = data.get("nextCursor") if isinstance(data, dict) else None
            if cursor is None or cursor == "":
                return result
            if not isinstance(cursor, str) or cursor in seen:
                raise RoEtollApiError(
                    "eToll returned a repeated or invalid pagination cursor."
                )
            seen.add(cursor)
            params["cursor"] = cursor
        raise RoEtollApiError(
            "eToll pagination limit reached; refusing to report incomplete data."
        )

    async def get_profile(self) -> dict:
        profiles = self._items(await self._request("GET", "/api/profiles"), "profiles")
        if any(not profile.get("id") for profile in profiles):
            raise RoEtollApiError("eToll returned a profile without its ID.")
        current = [p for p in profiles if p.get("isCurrent") is True]
        if len(current) == 1:
            return current[0]
        if len(profiles) == 1:
            return profiles[0]
        raise RoEtollProfileError(
            "Create/select a current profile in the eToll portal first."
        )

    async def get_vehicles(self) -> list[dict]:
        vehicles = await self._collection(
            "/api/vehicles",
            "vehicles",
            {
                "vehicleType": "CAR",
                "computeVignetteEligibility": "true",
                "size": PAGE_SIZE,
            },
        )
        unique: dict[str, dict] = {}
        for vehicle in vehicles:
            if (
                not vehicle.get("id")
                or not isinstance(vehicle.get("plateNumber"), str)
                or not vehicle["plateNumber"].strip()
            ):
                raise RoEtollApiError(
                    "eToll returned a vehicle without its ID or plate number."
                )
            unique[str(vehicle["id"])] = vehicle
        return list(unique.values())

    async def verify_vehicle(self, vehicle_id: str, toll_type: str) -> dict:
        """Request one verification type, matching the portal's ForType method."""
        if toll_type not in {"VIGNETTE", "BRIDGE"}:
            raise RoEtollApiError("Unsupported toll verification type.")
        data = await self._request(
            "POST",
            "/api/tolls/verification",
            json={
                "vehicleId": vehicle_id,
                "types": [toll_type],
            },
        )
        if not isinstance(data, dict) or toll_type.lower() not in data:
            raise RoEtollApiError("eToll returned an unexpected verification response.")
        vehicle = data.get("vehicle")
        if (
            isinstance(vehicle, dict)
            and vehicle.get("vehicleId") is not None
            and str(vehicle["vehicleId"]) != str(vehicle_id)
        ):
            raise RoEtollApiError(
                "eToll returned verification for a different vehicle."
            )
        return data

    async def get_countries(self) -> list[dict]:
        return self._items(
            await self._request("GET", "/api/resources/countries"), "countries"
        )

    async def verify_bridge_by_plate(self, vehicle: dict) -> dict:
        """Use the portal's read-only ForTypedVehicle request for bridge recovery."""
        if not all(
            isinstance(vehicle.get(key), str) and vehicle[key].strip()
            for key in ("plateNumber", "countryCode")
        ):
            raise RoEtollApiError("Bridge lookup requires a plate and country.")
        payload = {
            "plateNumber": vehicle["plateNumber"].strip(),
            "countryCode": vehicle["countryCode"].strip(),
            "vin": vehicle.get("vin") if isinstance(vehicle.get("vin"), str) else None,
            "types": ["BRIDGE"],
        }
        data = await self._request("POST", "/api/tolls/verification", json=payload)
        if not isinstance(data, dict) or not isinstance(data.get("bridge"), dict):
            raise RoEtollApiError("eToll returned an unexpected bridge response.")
        if data["bridge"].get("status") == "OK":
            # A plate lookup must identify the same vehicle before we expose values.
            returned = data.get("vehicle")
            if not isinstance(returned, dict) or any(
                not isinstance(returned.get(key), str)
                or "".join(returned[key].split()).casefold()
                != "".join(payload[key].split()).casefold()
                for key in ("plateNumber", "countryCode")
            ):
                raise RoEtollApiError("eToll bridge response vehicle did not match.")
            if (
                payload["vin"]
                and returned.get("vin") is not None
                and (
                    not isinstance(returned["vin"], str)
                    or returned["vin"].strip().casefold()
                    != payload["vin"].strip().casefold()
                )
            ):
                raise RoEtollApiError("eToll bridge response vehicle did not match.")
        return data

    async def get_invoices(self, start: datetime, end: datetime) -> list[dict]:
        def iso(value: datetime) -> str:
            return (
                value.astimezone(timezone.utc)
                .isoformat(timespec="milliseconds")
                .replace("+00:00", "Z")
            )

        return await self._collection(
            "/api/invoices", "invoices", {"from": iso(start), "to": iso(end)}
        )
