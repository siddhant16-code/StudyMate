from pathlib import Path

from pypdf import PdfReader
from docx import Document


def extract_text(file_path):
    """
    Extract readable text from PDF, DOCX and TXT files.
    """

    path = Path(file_path)
    extension = path.suffix.lower()

    try:

        # PDF files
        if extension == ".pdf":

            reader = PdfReader(str(path))

            text = []

            for page_number, page in enumerate(reader.pages, start=1):
                page_text = page.extract_text() or ""

                if page_text.strip():
                    text.append(
                        f"\n--- Page {page_number} ---\n{page_text}"
                    )

            extracted_text = "\n".join(text)

        # Word documents
        elif extension == ".docx":

            document = Document(str(path))

            extracted_text = "\n".join(
                paragraph.text
                for paragraph in document.paragraphs
                if paragraph.text.strip()
            )

        # Text files
        elif extension == ".txt":

            extracted_text = path.read_text(
                encoding="utf-8",
                errors="replace"
            )

        else:
            raise ValueError("Unsupported file format.")

        if not extracted_text.strip():
            raise ValueError(
                "No readable text found in this document."
            )

        # Prevent excessively large documents from overwhelming AI.
        max_characters = 30000

        if len(extracted_text) > max_characters:
            extracted_text = (
                extracted_text[:max_characters]
                + "\n\n[Document shortened for AI analysis.]"
            )

        return extracted_text

    except Exception as error:
        raise RuntimeError(
            f"Could not read {path.name}: {error}"
        ) from error