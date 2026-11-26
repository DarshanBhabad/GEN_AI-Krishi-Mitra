from datetime import datetime, timezone
from urllib.parse import urlsplit

import httpx

from app.core.config import settings


class LiveDataUnavailable(RuntimeError):
    pass


async def weather_for_location(location: str) -> dict:
    timeout = httpx.Timeout(8.0, connect=4.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        geo_response = await client.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": location, "count": 1, "language": "en", "format": "json"},
        )
        geo_response.raise_for_status()
        places = geo_response.json().get("results") or []
        if not places:
            raise LiveDataUnavailable("No matching location was found.")
        place = places[0]
        response = await client.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": place["latitude"],
                "longitude": place["longitude"],
                "current": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m",
                "daily": "precipitation_probability_max,temperature_2m_max,temperature_2m_min",
                "forecast_days": 1,
                "timezone": "auto",
            },
        )
        response.raise_for_status()
        data = response.json()
    return {
        "provider": "Open-Meteo",
        "location": ", ".join(part for part in (place.get("name"), place.get("admin1"), place.get("country")) if part),
        "observed_at": data.get("current", {}).get("time"),
        "current": data.get("current", {}),
        "daily": data.get("daily", {}),
        "attribution": "Open-Meteo",
    }


async def mandi_prices(commodity: str, market: str | None = None) -> dict:
    if not settings.mandi_api_url:
        raise LiveDataUnavailable(
            "A mandi data endpoint is not configured. Set MANDI_API_URL to an authorized provider."
        )
    parsed_url = urlsplit(settings.mandi_api_url)
    if parsed_url.scheme != "https" or not parsed_url.netloc:
        raise LiveDataUnavailable("The configured mandi endpoint must use HTTPS.")
    params = {"commodity": commodity}
    if market:
        params["market"] = market
    headers = {"Accept": "application/json"}
    if settings.mandi_api_key:
        headers["Authorization"] = f"Bearer {settings.mandi_api_key}"
    async with httpx.AsyncClient(timeout=httpx.Timeout(8.0, connect=4.0)) as client:
        response = await client.get(settings.mandi_api_url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()
    if not data:
        raise LiveDataUnavailable("The mandi provider returned no price records.")
    return {
        "provider": "Configured mandi API",
        "commodity": commodity,
        "market": market,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "data": data,
    }


def format_weather(data: dict, language: str) -> str:
    current = data["current"]
    temperature = current.get("temperature_2m")
    precipitation = current.get("precipitation")
    stamp = data.get("observed_at") or "time unavailable"
    if language == "mr":
        return (
            f"{data['location']} साठी Open-Meteo माहिती ({stamp}): सध्याचे तापमान "
            f"{temperature}°C, पर्जन्य {precipitation} mm. हा थेट हवामान डेटा आहे; "
            "कृषी सल्ला नाही."
        )
    return (
        f"{data['location']} के लिए Open-Meteo जानकारी ({stamp}): वर्तमान तापमान "
        f"{temperature}°C, वर्षा {precipitation} mm। यह लाइव मौसम डेटा है, कृषि सलाह नहीं।"
    )


def format_mandi(data: dict, language: str) -> str:
    if language == "mr":
        return f"{data['commodity']} साठी {data.get('market') or 'निवडलेल्या बाजारात'} बाजार डेटा ({data['retrieved_at']}): {data['data']}"
    return f"{data['commodity']} के लिए {data.get('market') or 'चुनी गई मंडी'} का बाजार डेटा ({data['retrieved_at']}): {data['data']}"
