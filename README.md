# Address Extraction Web App

A production-ready FastAPI-based web application that allows users to upload a PDF or TXT file, parses and extracts addresses using the Smarty US Extract API, and displays the structured US addresses in a premium, modern results table.

## Prerequisites

- Python 3.8 or higher
- pip (Python package installer)
- Smarty US Extract API credentials (Auth ID and Auth Token)

## Installation Steps

1. Clone or download the repository to your local machine.
2. Navigate into the project folder:
   ```bash
   cd address-extraction
   ```
3. Create a Python virtual environment:
   ```bash
   python -m venv venv
   ```
4. Activate the virtual environment:
   - **Windows (PowerShell):**
     ```powershell
     .\venv\Scripts\Activate.ps1
     ```
   - **Windows (CMD):**
     ```cmd
     .\venv\Scripts\activate.bat
     ```
   - **macOS / Linux:**
     ```bash
     source venv/bin/activate
     ```
5. Install the required Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Environment Setup

1. In the `address-extraction` root directory, copy the `.env.example` file to create a `.env` file:
   ```bash
   copy .env.example .env
   ```
   *(Or `cp .env.example .env` on macOS/Linux)*
2. Open the new `.env` file and insert your Smarty US Extract API authentication credentials:
   ```env
   SMARTY_AUTH_ID=your-smarty-auth-id-here
   SMARTY_AUTH_TOKEN=your-smarty-auth-token-here
   ```

## How to Run

Start the FastAPI application server using `uvicorn`:
```bash
uvicorn main:app --reload
```
The server will start running locally at: `http://127.0.0.1:8000`

## How to Use

1. Open your web browser and navigate to `http://127.0.0.1:8000`.
2. Drag and drop a PDF or TXT file into the upload zone, or click **Browse Files** to select one.
3. Click **Extract Addresses** to initiate the processing.
4. Once completed, the parsed results will be displayed in a table below the form showing the raw address and its structured components (Street, City, State, Zip).
5. You can also click **Copy JSON** to copy the raw API response output directly to your clipboard.

## API Documentation Note

FastAPI automatically generates interactive Swagger API documentation. You can view it and test endpoints directly by opening:
`http://127.0.0.1:8000/docs`
