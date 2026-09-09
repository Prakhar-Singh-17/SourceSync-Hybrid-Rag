"""Turning a public GitHub repository archive into passages.

A repository is mostly noise for retrieval purposes: lock files, build output,
vendored dependencies, images.  Indexing all of it wastes embedding calls and,
worse, buries the handful of files that actually answer questions.  So the
archive is filtered down to source and documentation files first.
"""

from urllib.parse import urlparse
from zipfile import ZipFile

from app.core.chunking import split_code, split_prose
from app.core.errors import SourceError, SourceTooLarge
from app.core.models import Passage

# Limits chosen for the free tier: the archive is buffered in memory, and every
# passage costs an embedding call and a slot in the Qdrant collection.
MAX_ARCHIVE_BYTES = 20 * 1024 * 1024
MAX_ELIGIBLE_FILES = 400
MAX_FILE_BYTES = 256 * 1024

CODE_EXTENSIONS = {
    ".c", ".cpp", ".cs", ".css", ".go", ".h", ".html", ".java", ".js", ".jsx",
    ".json", ".kt", ".php", ".py", ".r", ".rb", ".rs", ".sh", ".sql", ".swift",
    ".toml", ".ts", ".tsx", ".vue", ".xml", ".yaml", ".yml",
}
PROSE_EXTENSIONS = {".md", ".rst", ".txt"}
ELIGIBLE_FILENAMES = {"dockerfile", "license", "makefile", "readme"}
IGNORED_DIRECTORIES = {
    ".git", ".github", ".venv", "__pycache__", "build", "coverage", "dist",
    "node_modules", "target", "vendor",
}
IGNORED_FILENAMES = {"package-lock.json", "yarn.lock", "uv.lock", "poetry.lock", "cargo.lock"}


def validate_github_url(url: str) -> dict[str, str]:
    """Accept only ``https://github.com/owner/repository`` and normalise it."""
    parsed = urlparse(url.strip())
    if parsed.scheme != "https" or parsed.netloc.lower() != "github.com":
        raise SourceError("Only public HTTPS GitHub repository URLs are supported.")
    if parsed.query or parsed.fragment:
        raise SourceError("Repository URLs must not contain a query string or fragment.")

    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) != 2:
        raise SourceError("Use a URL in the form https://github.com/owner/repository.")

    owner, repository = parts[0], parts[1].removesuffix(".git")
    if not repository:
        raise SourceError("Use a URL in the form https://github.com/owner/repository.")
    return {
        "owner": owner,
        "repository": repository,
        "name": f"{owner}/{repository}",
        "url": f"https://github.com/{owner}/{repository}",
    }


def eligible_members(archive: ZipFile) -> list[str]:
    """List the files inside the archive that are worth indexing."""
    members: list[str] = []
    for info in archive.infolist():
        path = info.filename.replace("\\", "/")
        parts = path.split("/")
        filename = parts[-1].lower()

        if info.is_dir() or info.file_size > MAX_FILE_BYTES:
            continue
        if filename in IGNORED_FILENAMES:
            continue
        if any(part.lower() in IGNORED_DIRECTORIES for part in parts[:-1]):
            continue
        if _extension(filename) not in CODE_EXTENSIONS | PROSE_EXTENSIONS:
            if filename not in ELIGIBLE_FILENAMES:
                continue

        members.append(path)
        if len(members) > MAX_ELIGIBLE_FILES:
            raise SourceTooLarge(
                f"Repositories may contain at most {MAX_ELIGIBLE_FILES} indexable files."
            )
    return members


def passages_from_file(path: str, text: str, repository_name: str) -> list[Passage]:
    """Chunk one repository file, using the line-aware splitter for code."""
    split = split_prose if _extension(path.split("/")[-1].lower()) in PROSE_EXTENSIONS else split_code
    return [
        Passage(text=chunk, index=index, source_name=repository_name, file_path=_strip_root(path))
        for index, chunk in enumerate(split(text))
    ]


def _extension(filename: str) -> str:
    return "." + filename.rsplit(".", 1)[-1] if "." in filename else ""


def _strip_root(path: str) -> str:
    """GitHub zipballs nest everything under ``owner-repo-sha/``; drop that prefix."""
    _, separator, remainder = path.partition("/")
    return remainder if separator else path
