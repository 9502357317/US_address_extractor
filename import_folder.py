import os
import sys
import requests

def main():
    if len(sys.argv) < 2:
        print("Usage: python import_folder.py <folder_path> [api_url]")
        sys.exit(1)

    folder_path = sys.argv[1]
    api_url = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:8000/extract"

    if not os.path.isdir(folder_path):
        print(f"Error: {folder_path} is not a directory.")
        sys.exit(1)

    # Find all PDF files (case-insensitive)
    files_to_process = []
    for root, _, files in os.walk(folder_path):
        for file in files:
            if file.lower().endswith(".pdf"):
                files_to_process.append(os.path.join(root, file))

    # Sort files by name to ensure consistent processed ordering
    files_to_process.sort(key=lambda p: os.path.basename(p).lower())

    if not files_to_process:
        print(f"No PDF files found in '{folder_path}'.")
        return

    print(f"Found {len(files_to_process)} PDF files to import.\n")

    processed = 0
    duplicate = 0
    failed = 0

    for file_path in files_to_process:
        filename = os.path.basename(file_path)
        try:
            with open(file_path, "rb") as f:
                files = {"file": (filename, f, "application/pdf")}
                response = requests.post(api_url, files=files)

            if response.status_code == 200:
                print(f"{filename}: PROCESSED")
                processed += 1
            elif response.status_code == 409:
                print(f"{filename}: DUPLICATE")
                duplicate += 1
            else:
                try:
                    error_detail = response.json().get("error", response.text)
                except Exception:
                    error_detail = response.text
                print(f"{filename}: FAILED (HTTP {response.status_code}: {error_detail})")
                failed += 1
        except Exception as e:
            print(f"{filename}: FAILED (Error: {e})")
            failed += 1

    print("\n" + "=" * 30)
    print("Import Summary")
    print("=" * 30)
    print(f"Processed: {processed}")
    print(f"Duplicate: {duplicate}")
    print(f"Failed:    {failed}")
    print("=" * 30)

if __name__ == "__main__":
    main()
