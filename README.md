# Address Extraction Web App & Address Registry

A production-ready FastAPI-based web application that allows users to upload PDF or TXT files, parse and extract addresses using the Smarty US Extract API, and manage the extracted addresses through a feature-rich Address Registry dashboard.

This application is built with a SQLite database backend, SQLAlchemy ORM, and has been extended to support several advanced document processing, deduplication, search, and human review features.

---

## Task Implementation Details

### 📂 Document Parsing & Failure Persistence
*   **Task 2: Persist Failures**: When a document contains no valid US addresses, rather than discarding the upload event, it is persisted to the database registry with a status of `"failed"` and a clear `failure_reason` (e.g., `"No US addresses were found in the document."`).
*   **Task 3: SHA-256 Byte-Level Deduplication**: Before processing an uploaded file, the server computes its SHA-256 hash. If a file with the same hash already exists in the registry, the upload is rejected with a `409 Conflict` response to prevent redundant processing.
*   **Task 11: Content-Level Deduplication**: If files have different filenames or minor whitespace variations but contain the same text content, the application collapses the text (collapsing all consecutive whitespace and newlines to single spaces and converting to lowercase) and hashes the result. Uploading a content-level duplicate is rejected with a `409 Conflict`.
*   **Concurrency & Chunking**: To prevent timeouts and stay within API payload size restrictions, large documents are split into smaller chunks on sentence/word boundaries. These chunks are processed concurrently in parallel.

### 🔍 Address registry, FTS5 Search & Filtering
*   **Task 4: Normalization**: Extracted address components (Street, City, State, Zip) are normalized to uppercase, stripped of leading/trailing spaces, and stored as structured fields. A unified `normalized` address string is automatically derived from these components.
*   **Task 5, 6, 7 & 13: Registry search, pagination, and statistics**:
    *   **Search**: Fully integrated SQLite **FTS5** (Full-Text Search) matching on address strings (e.g., searching `River` returns `Riverside`).
    *   **Filters**: Dropdown filter options for `City`, `State`, and `Zip` derived dynamically from the registry database.
    *   **Pagination**: Paginated endpoints accepting `limit` and `offset` parameters to cleanly page through thousands of entries.
    *   **Dashboard Stats**: A `/stats` endpoint tracking the number of processed documents, failed documents, active addresses, duplicate files blocked, and near-duplicate addresses resolved.
*   **Task 10: CSV Export**: Users can stream and download a CSV file containing active address records that match their active search queries and filters.

### 👥 Human Review & Fuzzy Matching Queue
*   **Task 8: Fuzzy Matching (Near-Duplicates)**: When a new address is extracted, the application runs a similarity check against existing database records. If the address matches an existing entry with a high similarity score (e.g., > 90% similarity, representing typos like `3900 Mian St` instead of `3900 Main St`), a `DuplicateCandidate` record is registered.
*   **Task 9: Human Review Queue**:
    *   **Review Dashboard**: Allows administrators to view duplicate candidates side-by-side.
    *   **Resolve Action**: Reviewers can choose to `merge` (which repoints all document links from the typo-address to the correct address, marks the typo-address as `merged`, and marks the correct address as `verified`) or dismiss the candidate as `not_duplicate`.
    *   **Address Component Editing**: Reviewers can patch individual address fields (e.g., fixing a typo on `Street` or `Zip`), which automatically re-derives the full normalized address.

### 💻 CLI Utilities
*   **Task 12: Bulk Import CLI (`import_folder.py`)**: A command line utility that recursively scans a specified folder, sorts all PDF documents alphabetically, uploads them sequentially to the server's API, and prints a final import summary of processed, duplicate, and failed files.

---

## Tech Stack & Prerequisites

*   **Backend**: Python 3.8+ / FastAPI / SQLAlchemy / SQLite (with FTS5 support)
*   **Frontend**: Vanilla HTML5 / CSS3 (vibrant styling & glassmorphism details) / Modern Javascript (ES6)
*   **Dependencies**: `requests`, `fastapi`, `uvicorn`, `pydantic`, `sqlalchemy`, `pypdf`, `python-multipart`

---

## Installation & Setup

1.  **Clone or download** this repository to your local machine.
2.  **Navigate** to the project directory:
    ```bash
    cd address-extraction
    ```
3.  **Create** a Python virtual environment:
    ```bash
    python -m venv venv
    ```
4.  **Activate** the virtual environment:
    *   **Windows (PowerShell):**
        ```powershell
        .\venv\Scripts\Activate.ps1
        ```
    *   **Windows (CMD):**
        ```cmd
        .\venv\Scripts\activate.bat
        ```
    *   **macOS / Linux:**
        ```bash
        source venv/bin/activate
        ```
5.  **Install** dependencies:
    ```bash
    pip install -r requirements.txt
    ```

---

## Environment Configuration

1.  Create a `.env` file from the example:
    ```bash
    copy .env.example .env
    ```
    *(Or `cp .env.example .env` on macOS/Linux)*
2.  Fill in your Smarty US Extract API credentials inside the `.env` file:
    ```env
    SMARTY_AUTH_ID=your-smarty-auth-id-here
    SMARTY_AUTH_TOKEN=your-smarty-auth-token-here
    ```

---

## Running the Application

### Running the FastAPI Server
Start the development server with:
```bash
uvicorn main:app --reload
```
Open your browser and navigate to: **`http://127.0.0.1:8000`**

### Running the Test Suite
To execute the comprehensive suite of tests in [test_app.py](file:///d:/surya/DataFactzProjects/Surya's_Task1/Surya's_Task1/address-extraction/test_app.py):
```bash
python -m unittest test_app.py
```

### Running the CLI Bulk Importer
```bash
python import_folder.py <folder_path_containing_pdfs> [api_url]
```
*(For example: `python import_folder.py .\Test_data`)*

---

## Interactive API Docs
FastAPI automatically provides interactive Swagger documentation. You can test endpoints directly by navigating to:
**`http://127.0.0.1:8000/docs`**
