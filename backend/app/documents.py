from io import BytesIO
from pathlib import PurePath

from fastapi import HTTPException, UploadFile, status
from pypdf import PdfReader

from app.chunking import split_text


MAX_DOCUMENT_BYTES = 25 * 1024 * 1024
MAX_PDF_PAGES = 150
ALLOWED_EXTENSIONS = {".pdf", ".txt"}


def extract_text(content: bytes, extension: str) -> tuple[str, int | None]:
    if extension == ".txt":
        try:
            return content.decode("utf-8"), None
        except UnicodeDecodeError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="TXT documents must use UTF-8 encoding.",
            ) from error

    try:
        pages = PdfReader(BytesIO(content)).pages
        return "\n\n".join(page.extract_text() or "" for page in pages), len(pages)
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The PDF could not be read.",
        ) from error


async def validate_document(upload: UploadFile) -> dict[str, int | str]:
    filename = upload.filename or ""
    extension = PurePath(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only PDF and TXT documents are supported.",
        )

    content = await upload.read(MAX_DOCUMENT_BYTES + 1)
    if len(content) > MAX_DOCUMENT_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Documents must be 25 MB or smaller.",
        )

    if extension == ".txt":
        text, _ = extract_text(content, extension)
        return {
            "filename": filename,
            "file_type": "txt",
            "size_bytes": len(content),
            "text_length": len(text),
            "chunk_count": len(split_text(text)),
        }

    text, page_count = extract_text(content, extension)
    assert page_count is not None
    if page_count > MAX_PDF_PAGES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="PDF documents must contain 150 pages or fewer.",
        )
    return {
        "filename": filename,
        "file_type": "pdf",
        "size_bytes": len(content),
        "page_count": page_count,
        "text_length": len(text),
        "chunk_count": len(split_text(text)),
    }