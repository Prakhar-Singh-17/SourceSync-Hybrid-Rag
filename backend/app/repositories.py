from urllib.parse import urlparse
from zipfile import ZipFile

from fastapi import HTTPException, status


MAX_ARCHIVE_BYTES = 50 * 1024 * 1024
MAX_ELIGIBLE_FILES = 5_000
MAX_FILE_BYTES = 1 * 1024 * 1024
ELIGIBLE_EXTENSIONS = {
    ".c", ".cpp", ".css", ".go", ".h", ".html", ".java", ".js", ".jsx",
    ".json", ".md", ".py", ".r", ".rb", ".rs", ".sql", ".toml", ".ts",
    ".tsx", ".txt", ".vue", ".xml", ".yaml", ".yml",
}
ELIGIBLE_FILENAMES = {"dockerfile", "license", "makefile", "readme"}
IGNORED_DIRECTORY_NAMES = {".git", "node_modules", "dist", "build", "coverage", "vendor"}


def eligible_members(archive: ZipFile) -> list[str]:
    members: list[str] = []
    for info in archive.infolist():
        path = info.filename.replace("\\", "/")
        parts = path.split("/")
        extension = "." + parts[-1].rsplit(".", 1)[-1].lower() if "." in parts[-1] else ""
        filename = parts[-1].lower()
        if info.is_dir() or info.file_size > MAX_FILE_BYTES:
            continue
        if extension not in ELIGIBLE_EXTENSIONS and filename not in ELIGIBLE_FILENAMES:
            continue
        if any(part.lower() in IGNORED_DIRECTORY_NAMES for part in parts[:-1]):
            continue
        members.append(path)
        if len(members) > MAX_ELIGIBLE_FILES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Repositories may contain at most 5,000 eligible files.",
            )
    return members


def validate_github_url(url: str) -> dict[str, str]:
    parsed = urlparse(url.strip())
    if parsed.scheme != "https" or parsed.netloc.lower() != "github.com":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Only public HTTPS GitHub repository URLs are supported.",
        )

    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) != 2 or parts[1].endswith(".git") is False:
        if len(parts) != 2:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Use a repository URL in the form https://github.com/owner/repository.",
            )
    repository = parts[1].removesuffix(".git")
    if not repository or parsed.query or parsed.fragment:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Repository URLs must point directly to a public GitHub repository.",
        )

    normalized_url = f"https://github.com/{parts[0]}/{repository}"
    return {"owner": parts[0], "repository": repository, "url": normalized_url}
