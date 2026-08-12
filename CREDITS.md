# Credits and attribution

**fbtv** ([cbodden/fbtv](https://github.com/cbodden/fbtv)) is an independent Emby/Jellyfin-oriented sidecar. It does **not** redistribute Fubo content and is not affiliated with FuboTV, Emby, Jellyfin, or the authors of the projects below. Credit is due to the communities and libraries that made the approach practical.

## Prior art and inspiration

Fubo authentication headers, device-id persistence, channel-lineup discovery, DRM skip heuristics, live stream resolution, and **guide EPG** patterns (`/epg` assets payloads, `papi/v1/guide/epg`) were informed by community “vlc-bridge” / Channels DVR bridge work:

| Project | Authors / maintainers | Notes |
| --- | --- | --- |
| [Yankees4life/vlc-bridge-fubo](https://gitlab.com/Yankees4life/vlc-bridge-fubo) | Yankees4life and contributors | Reference Python client for sign-in, plan/subscription channel lists, and `vapi/asset` watch URLs |
| [maus-me/vlc-bridge-fubo](https://github.com/maus-me/vlc-bridge-fubo) | maus-me and contributors | Continued bridge packaging and playlist serving patterns |
| [jgomez177/vlc-bridge-fubo](https://hub.docker.com/r/jgomez177/vlc-bridge-fubo) | joagomez / jgomez177 | Widely shared Docker image and Channels DVR discussion that popularized the bridge model |
| [Fubo TV project (Channels Community)](https://community.getchannels.com/t/fubo-tv-project/37533) | Community thread participants | Practical notes on DRM limits, IP-bound streams, playlists, and guide mapping |
| Earlier vlc-bridge / IPTV bridge work (e.g. miibeez lineage referenced in that thread) | Respective authors | General playlist/watch proxy structure for live TV players |

This repository reimplements those ideas for **Emby and Jellyfin** (native M3U tuner + XMLTV) with FastAPI. It is not a fork of the projects above; please consult each project for its own license and terms.

## Platforms and formats

| Name | Role |
| --- | --- |
| [Emby](https://emby.media/) | First-class target; Live TV M3U tuner and XMLTV guide providers |
| [Jellyfin](https://jellyfin.org/) | First-class target; Live TV M3U tuner and XMLTV guide providers |
| [Fubo](https://www.fubo.tv/) | Live TV service accessed via the subscriber’s own account (unofficial/private API) |
| [XMLTV](http://wiki.xmltv.org/) | EPG file format used by `/epg.xml` |
| M3U / HLS | Playlist and stream formats consumed by Emby and Jellyfin |

Emby, Jellyfin, and Fubo are trademarks of their respective owners.

## Third-party Python dependencies

Runtime dependencies are declared in `requirements.txt`. Licenses below are as commonly published by each project; verify upstream if you redistribute binaries.

| Package | Project | Typical license | Use in this repo |
| --- | --- | --- | --- |
| [FastAPI](https://fastapi.tiangolo.com/) | Sebastián Ramírez / tiangolo | MIT | HTTP API |
| [Uvicorn](https://www.uvicorn.org/) | Encode / Tom Christie et al. | BSD-3-Clause | ASGI server |
| [HTTPX](https://www.python-httpx.org/) | Encode | BSD-3-Clause | Fubo HTTP client |
| [python-dotenv](https://github.com/theskumar/python-dotenv) | theskumar et al. | BSD-3-Clause | `.env` loading |

Transitive dependencies (Starlette, Pydantic, AnyIO, h11, httpcore, certifi, etc.) ship with those packages and retain their own copyright notices.

## Documentation conventions

| Resource | Use |
| --- | --- |
| [Keep a Changelog](https://keepachangelog.com/) | Structure of `CHANGELOG.md` |
| [Semantic Versioning](https://semver.org/) | Version numbering |

## Disclaimer

Using unofficial APIs may violate a provider’s terms of service. This software is intended for personal use with **your own** paid Fubo subscription. Authors of credited projects are not responsible for how this bridge is used.

## Updating this file

When adding a dependency or adopting another project’s approach, update this file and note the change in `CHANGELOG.md`.
