from fastapi import HTTPException, UploadFile
import os
import tempfile
import PyPDF2

class FileParser:
    @staticmethod
    def extract_pdf_text(file_path: str) -> str:
        """
        Use PyPDF2 library to extract text from ALL pages.
        Return full text as string.
        If PDF is corrupted/unreadable, raise HTTPException(400)
        """
        try:
            reader = PyPDF2.PdfReader(file_path)
            text = ""
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            return text
        except Exception:
            raise HTTPException(
                status_code=400,
                detail="This PDF is damaged or cannot be read. Please try another file."
            )

    @staticmethod
    def extract_txt_text(file_path: str) -> str:
        """
        Read file with UTF-8 encoding.
        Return text as string.
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            raise HTTPException(
                status_code=400,
                detail="This PDF is damaged or cannot be read. Please try another file."  # Fallback detail
            )

    @staticmethod
    def read_file(file: UploadFile) -> str:
        """
        Check file extension, route to extract_pdf_text or extract_txt_text.
        Return extracted text string.
        """
        filename = file.filename or ""
        _, ext = os.path.splitext(filename.lower())
        
        # Write UploadFile stream to temporary file to work with file paths
        temp_fd, temp_path = tempfile.mkstemp(suffix=ext)
        try:
            file.file.seek(0)
            content = file.file.read()
            with os.fdopen(temp_fd, "wb") as temp_file:
                temp_file.write(content)
            
            if ext == ".pdf":
                return FileParser.extract_pdf_text(temp_path)
            elif ext == ".txt":
                return FileParser.extract_txt_text(temp_path)
            else:
                raise HTTPException(
                    status_code=400,
                    detail="Only PDF and TXT files are allowed."
                )
        finally:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
