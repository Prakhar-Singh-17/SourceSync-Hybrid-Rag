"""Downloading a public GitHub repository as a zip archive.

GitHub exposes a zipball endpoint for every public repository, which avoids
shelling out to git and avoids writing anything to disk -- useful on a free
Render instance with an ephemeral filesystem.
"""

import logging

import httpx

from app.core.errors import SourceError, SourceTooLarge
from app.core.repository import MAX_ARCHIVE_BYTES

logger = logging.getLogger(__name__)

DOWNLOAD_TIMEOUT_SECONDS = 60


async def download_archive(owner: str, repository: str) -> bytes:
    """Fetch ``owner/repository`` as a zip archive, refusing oversized downloads.

    The response is streamed and the size checked as it arrives, so a very large
    repository is abandoned after a few megabytes instead of being buffered in
    full and only then rejected.
    """
    url = f"https://api.github.com/repos/{owner}/{repository}/zipball"
    buffer = bytearray()
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=DOWNLOAD_TIMEOUT_SECONDS) as client:
            async with client.stream("GET", url, headers={"Accept": "application/vnd.github+json"}) as response:
                if response.status_code == 404:
                    raise SourceError(
                        "That repository was not found. It must exist and be public."
                    )
                response.raise_for_status()
                async for chunk in response.aiter_bytes():
                    buffer.extend(chunk)
                    if len(buffer) > MAX_ARCHIVE_BYTES:
                        raise SourceTooLarge(
                            f"Repository archives must be {MAX_ARCHIVE_BYTES // (1024 * 1024)} MB or smaller."
                        )
    except SourceError:
        raise
    except httpx.HTTPStatusError as error:
        logger.warning("GitHub returned %s for %s/%s", error.response.status_code, owner, repository)
        raise SourceError(
            f"GitHub returned HTTP {error.response.status_code} while downloading the repository."
        ) from error
    except httpx.HTTPError as error:
        logger.warning("GitHub download failed for %s/%s: %s", owner, repository, error)
        raise SourceError("The repository could not be downloaded from GitHub.") from error
    return bytes(buffer)
