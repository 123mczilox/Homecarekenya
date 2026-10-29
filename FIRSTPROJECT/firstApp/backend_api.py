import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen

from django.conf import settings

API_TIMEOUT_SECONDS = 5


class BackendAPIError(Exception):
    pass


def get_json(path, params=None):
    base_url = getattr(settings, "HOMECARE_API_BASE_URL", "")
    if not base_url:
        raise BackendAPIError("The backend API is not configured.")

    url = urljoin(f"{base_url}/", path.lstrip("/"))
    if params:
        url = f"{url}?{urlencode(params)}"
    request = Request(url, headers={"Accept": "application/json"})

    try:
        with urlopen(request, timeout=API_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (
        HTTPError,
        URLError,
        TimeoutError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as error:
        raise BackendAPIError("The backend service could not be reached.") from error

    return payload


def _public_home(record):
    if not isinstance(record, dict) or not record.get("slug") or not record.get("name"):
        return None

    return {
        "pk": record.get("id", ""),
        "slug": str(record["slug"]),
        "name": str(record["name"]),
        "location": str(record.get("location") or "Location not provided"),
        "descripttion": str(record.get("description") or ""),
        "is_verified": record.get("is_verified") is True,
    }


def get_public_homes(params=None):
    payload = get_json("/api/v1/homes/", params=params)
    records = payload.get("results", []) if isinstance(payload, dict) else payload
    if not isinstance(records, list):
        raise BackendAPIError("The backend returned an invalid homes response.")
    return [home for item in records if (home := _public_home(item)) is not None]


def get_public_home(slug):
    payload = get_json(f"/api/v1/homes/{slug}/")
    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        payload = payload["data"]
    home = _public_home(payload)
    if home is None:
        raise BackendAPIError("The backend returned an invalid home profile.")
    return home
