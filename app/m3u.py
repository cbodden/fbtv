"""M3U playlist builder for Emby and Jellyfin Live TV."""

from __future__ import annotations

from app.fubo_client import Channel


def build_m3u(channels: list[Channel], base_url: str) -> str:
    base = base_url.rstrip("/")
    lines = ["#EXTM3U", ""]

    for channel in channels:
        attrs = [
            f'tvg-id="{_escape_attr(channel.call_sign)}"',
            f'tvg-name="{_escape_attr(channel.name)}"',
            f'channel-id="{_escape_attr(channel.id)}"',
        ]
        if channel.logo:
            attrs.append(f'tvg-logo="{_escape_attr(channel.logo)}"')
        if channel.groups:
            group = ";".join(channel.groups)
            attrs.append(f'group-title="{_escape_attr(group)}"')

        lines.append(f"#EXTINF:-1 {' '.join(attrs)},{_escape_name(channel.name)}")
        lines.append(f"{base}/watch/{channel.id}")
        lines.append("")

    return "\r\n".join(lines)


def _escape_attr(value: str) -> str:
    return value.replace('"', "'").replace("\n", " ").strip()


def _escape_name(value: str) -> str:
    return value.replace("\n", " ").strip()
