"""Shared, side-effect-free validation for the server and Windows setup wizard."""

import json
import re


def parse_ice_servers(raw):
    try:
        items = json.loads(raw)
        if not isinstance(items, list) or len(items) > 5:
            raise ValueError
        for item in items:
            if not isinstance(item, dict):
                raise ValueError
            urls = item.get("urls")
            urls = [urls] if isinstance(urls, str) else urls
            if not isinstance(urls, list) or not urls or len(urls) > 10:
                raise ValueError
            if not all(
                isinstance(url, str)
                and re.fullmatch(r"(?:stun|turn|turns):[^\s]+", url)
                and url.split(":", 1)[1].strip("/")
                for url in urls
            ):
                raise ValueError
            for name in ("username", "credential"):
                if name in item and not isinstance(item[name], str):
                    raise ValueError
        return items
    except (ValueError, TypeError, AttributeError):
        raise ValueError("Invalid ICE server configuration") from None
