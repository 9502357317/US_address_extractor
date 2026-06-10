import uuid
import unittest
from unittest.mock import patch, MagicMock
import io
import requests
from fastapi.testclient import TestClient
from fastapi import HTTPException

import os
os.environ["TESTING"] = "1"
os.environ["SMARTY_AUTH_ID"] = "test-id"
os.environ["SMARTY_AUTH_TOKEN"] = "test-token"

from main import app
from app.services.file_parser import FileParser

class TestAddressExtractionApp(unittest.TestCase):
    def setUp(self):
        from app.db import Base, engine, init_db
        from sqlalchemy import text
        with engine.begin() as connection:
            connection.execute(text("DROP TABLE IF EXISTS addresses_fts"))
        Base.metadata.drop_all(bind=engine)
        init_db()
        self.client = TestClient(app)

    @patch("requests.post")
    def test_success_path(self, mock_post):
        # Setup mock for successful Smarty US Extract response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "addresses": [
                {
                    "text": "350 5th Ave, New York, NY 10118",
                    "api_output": [
                        {
                            "components": {
                                "primary_number": "350",
                                "street_name": "5th",
                                "street_suffix": "Ave",
                                "city_name": "New York",
                                "state_abbreviation": "NY",
                                "zipcode": "10118"
                            }
                        }
                    ]
                }
            ]
        }
        mock_post.return_value = mock_response

        # Call endpoint with a valid TXT file
        file_content = b"350 5th Ave, New York, NY 10118"
        files = {"file": ("test.txt", io.BytesIO(file_content), "text/plain")}
        
        response = self.client.post("/extract", files=files)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertTrue(data["success"])
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["addresses"][0]["input_text"], "350 5th Ave, New York, NY 10118")
        self.assertEqual(data["addresses"][0]["components"]["primary_number"], "350")
        self.assertEqual(data["addresses"][0]["components"]["zipcode"], "10118")

    @patch("requests.post")
    def test_duplicate_upload_returns_409_without_new_row(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "addresses": [
                {
                    "text": "987 Unique Duplicate Street, Boston, MA 02108",
                    "api_output": [
                        {
                            "components": {
                                "primary_number": "987",
                                "street_name": "Unique Duplicate",
                                "street_suffix": "Street",
                                "city_name": "Boston",
                                "state_abbreviation": "MA",
                                "zipcode": "02108",
                            }
                        }
                    ],
                }
            ]
        }
        mock_post.return_value = mock_response

        unique_text = (
            f"987 Unique Duplicate Street, Boston, MA 02108 "
            f"{uuid.uuid4()}"
        ).encode("utf-8")
        first_files = {
            "file": (
                "letter_riverside.txt",
                io.BytesIO(unique_text),
                "text/plain",
            )
        }
        second_files = {
            "file": (
                "exact_duplicate_of_letter_riverside.txt",
                io.BytesIO(unique_text),
                "text/plain",
            )
        }

        first_response = self.client.post("/extract", files=first_files)
        second_response = self.client.post("/extract", files=second_files)

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 409)
        self.assertEqual(
            second_response.json()["existing_document_id"],
            first_response.json()["document_id"],
        )
        self.assertEqual(mock_post.call_count, 1)

    @patch("requests.post")
    def test_content_level_duplicate_upload_returns_409(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "addresses": [
                {
                    "text": "1600 Amphitheatre Pkwy, Mountain View, CA 94043",
                    "api_output": [
                        {
                            "components": {
                                "primary_number": "1600",
                                "street_name": "Amphitheatre",
                                "street_suffix": "Pkwy",
                                "city_name": "Mountain View",
                                "state_abbreviation": "CA",
                                "zipcode": "94043"
                            }
                        }
                    ]
                }
            ]
        }
        mock_post.return_value = mock_response

        # First upload
        file_content_1 = b"1600 Amphitheatre Pkwy, Mountain View, CA 94043"
        files_1 = {"file": ("file1.txt", io.BytesIO(file_content_1), "text/plain")}
        
        response_1 = self.client.post("/extract", files=files_1)
        self.assertEqual(response_1.status_code, 200)

        # Second upload with different name and spacing/capitalization, but same collapsed content
        file_content_2 = b"  1600   AMPHITHEATRE   PKWY,\n Mountain View, ca 94043  "
        files_2 = {"file": ("file2_resaved.txt", io.BytesIO(file_content_2), "text/plain")}
        
        response_2 = self.client.post("/extract", files=files_2)
        self.assertEqual(response_2.status_code, 409)
        self.assertEqual(response_2.json()["error"], "This file has already been uploaded.")
        self.assertEqual(response_2.json()["existing_document_id"], response_1.json()["document_id"])

    @patch("requests.post")
    def test_failed_upload_is_persisted(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"addresses": []}
        mock_post.return_value = mock_response

        unique_text = (
            f"No address in this upload {uuid.uuid4()}"
        ).encode("utf-8")
        files = {
            "file": (
                "no_address_found.txt",
                io.BytesIO(unique_text),
                "text/plain",
            )
        }

        response = self.client.post("/extract", files=files)
        data = response.json()
        document_response = self.client.get(
            f"/documents/{data['document_id']}"
        )
        document = document_response.json()

        self.assertEqual(response.status_code, 400)
        self.assertEqual(document_response.status_code, 200)
        self.assertEqual(document["status"], "failed")
        self.assertEqual(
            document["failure_reason"],
            "No US addresses were found in the document.",
        )
        self.assertEqual(document["addresses"], [])

    @patch("requests.post")
    def test_error_1_smarty_401(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_post.return_value = mock_response

        files = {"file": ("test.txt", io.BytesIO(b"123 main st"), "text/plain")}
        response = self.client.post("/extract", files=files)
        self.assertEqual(response.status_code, 401)
        data = response.json()
        self.assertFalse(data["success"])
        self.assertEqual(data["error"], "Invalid API credentials. Please contact administrator.")

    @patch("requests.post")
    def test_error_2_smarty_402(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 402
        mock_response.text = "Payment Required"
        mock_post.return_value = mock_response

        files = {"file": ("test.txt", io.BytesIO(b"123 main st"), "text/plain")}
        response = self.client.post("/extract", files=files)
        self.assertEqual(response.status_code, 402)
        data = response.json()
        self.assertFalse(data["success"])
        self.assertEqual(data["error"], "API usage limit reached. Please try again later.")

    @patch("requests.post")
    def test_error_3_smarty_500(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal error"
        mock_post.return_value = mock_response

        files = {"file": ("test.txt", io.BytesIO(b"123 main st"), "text/plain")}
        response = self.client.post("/extract", files=files)
        self.assertEqual(response.status_code, 500)
        data = response.json()
        self.assertFalse(data["success"])
        self.assertEqual(data["error"], "Something went wrong on server. Please try again later.")

    @patch("requests.post")
    def test_error_smarty_413(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 413
        mock_response.text = "Payload Too Large"
        mock_post.return_value = mock_response

        files = {"file": ("test.txt", io.BytesIO(b"123 main st"), "text/plain")}
        response = self.client.post("/extract", files=files)
        self.assertEqual(response.status_code, 413)
        data = response.json()
        self.assertFalse(data["success"])
        self.assertEqual(data["error"], "The file is too large to process. Please upload a smaller document.")

    def test_error_4_unsupported_file_type(self):
        files = {"file": ("test.png", io.BytesIO(b"fake image content"), "image/png")}
        response = self.client.post("/extract", files=files)
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data["success"])
        self.assertEqual(data["error"], "Only PDF and TXT files are allowed.")

    def test_error_5_empty_file(self):
        files = {"file": ("test.txt", io.BytesIO(b""), "text/plain")}
        response = self.client.post("/extract", files=files)
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data["success"])
        self.assertEqual(data["error"], "The uploaded file is empty.")

    def test_error_6_file_too_large(self):
        # 10 MB = 10,485,760 bytes. Let's make it slightly larger.
        large_content = b"x" * (10 * 1024 * 1024 + 100)
        files = {"file": ("test.txt", io.BytesIO(large_content), "text/plain")}
        response = self.client.post("/extract", files=files)
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data["success"])
        self.assertEqual(data["error"], "File size is too large. Please upload a smaller file.")

    @patch("app.services.file_parser.FileParser.read_file")
    def test_error_7_text_too_large(self, mock_read_file):
        # Text limit is 10 MB. Mock the read file to return text > 10 MB.
        mock_read_file.return_value = "x" * (10 * 1024 * 1024 + 100)
        files = {"file": ("test.txt", io.BytesIO(b"dummy content"), "text/plain")}
        response = self.client.post("/extract", files=files)
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data["success"])
        self.assertEqual(data["error"], "The file is too large to process. Please upload a smaller document.")

    def test_error_8_corrupted_pdf(self):
        corrupted_content = b"%PDF-1.4 damaged pdf bytes"
        files = {"file": ("damaged.pdf", io.BytesIO(corrupted_content), "application/pdf")}
        response = self.client.post("/extract", files=files)
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data["success"])
        self.assertEqual(data["error"], "This PDF is damaged or cannot be read. Please try another file.")

    @patch("requests.post")
    def test_error_9_no_addresses_found(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "addresses": []
        }
        mock_post.return_value = mock_response

        files = {"file": ("test.txt", io.BytesIO(b"Hello there is no address here"), "text/plain")}
        response = self.client.post("/extract", files=files)
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data["success"])
        self.assertEqual(data["error"], "No US addresses were found in the document.")

    @patch("requests.post")
    def test_error_10_network_timeout(self, mock_post):
        mock_post.side_effect = requests.Timeout("Connection timed out")

        files = {"file": ("test.txt", io.BytesIO(b"123 main st"), "text/plain")}
        response = self.client.post("/extract", files=files)
        self.assertEqual(response.status_code, 503)
        data = response.json()
        self.assertFalse(data["success"])
        self.assertEqual(data["error"], "Unable to connect to API. Please try again later.")

    @patch("requests.post")
    def test_error_11_malformed_api_json(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        # .json() raising ValueError simulates malformed JSON
        mock_response.json.side_effect = ValueError("No JSON object could be decoded")
        mock_post.return_value = mock_response

        files = {"file": ("test.txt", io.BytesIO(b"123 main st"), "text/plain")}
        response = self.client.post("/extract", files=files)
        self.assertEqual(response.status_code, 500)
        data = response.json()
        self.assertFalse(data["success"])
        self.assertEqual(data["error"], "Unexpected response from API. Please try again.")

    @patch("requests.post")
    def test_success_chunking(self, mock_post):
        # Setup mocks for multiple successful Smarty responses
        mock_response_1 = MagicMock()
        mock_response_1.status_code = 200
        mock_response_1.json.return_value = {
            "addresses": [
                {
                    "text": "123 Chunk One St, New York, NY 10001",
                    "api_output": [
                        {
                            "components": {
                                "primary_number": "123",
                                "street_name": "Chunk One",
                                "street_suffix": "St",
                                "city_name": "New York",
                                "state_abbreviation": "NY",
                                "zipcode": "10001"
                            }
                        }
                    ]
                }
            ]
        }

        mock_response_2 = MagicMock()
        mock_response_2.status_code = 200
        mock_response_2.json.return_value = {
            "addresses": [
                {
                    "text": "456 Chunk Two Rd, San Francisco, CA 94102",
                    "api_output": [
                        {
                            "components": {
                                "primary_number": "456",
                                "street_name": "Chunk Two",
                                "street_suffix": "Rd",
                                "city_name": "San Francisco",
                                "state_abbreviation": "CA",
                                "zipcode": "94102"
                            }
                        }
                    ]
                }
            ]
        }

        # Sequence of responses for consecutive chunk posts
        mock_post.side_effect = [mock_response_1, mock_response_2]

        from app.services.address_service import AddressService
        original_chunk_text = AddressService.chunk_text
        
        # Override chunk_text with a small max_chunk_size_bytes to trigger chunking for a short string
        def mock_chunk_text(text, max_chunk_size_bytes=60000):
            return original_chunk_text(text, max_chunk_size_bytes=50)

        with patch.object(AddressService, "chunk_text", side_effect=mock_chunk_text):
            file_content = b"123 Chunk One St, New York, NY 10001\n456 Chunk Two Rd, San Francisco, CA 94102\n"
            files = {"file": ("test.txt", io.BytesIO(file_content), "text/plain")}
            
            response = self.client.post("/extract", files=files)
            self.assertEqual(response.status_code, 200)
            data = response.json()
            
            self.assertTrue(data["success"])
            self.assertEqual(data["count"], 2)
            self.assertEqual(data["addresses"][0]["input_text"], "123 Chunk One St, New York, NY 10001")
            self.assertEqual(data["addresses"][1]["input_text"], "456 Chunk Two Rd, San Francisco, CA 94102")

    def test_infinite_loop_prevention(self):
        # Verify that chunk_text handles extremely long inputs and potentially invalid sequences without loops
        from app.services.address_service import AddressService
        # A long sequence that has no spaces but exceeds chunk limit (e.g. 100 bytes)
        long_string = "a" * 150
        # If it doesn't infinite loop, this call completes immediately
        chunks = AddressService.chunk_text(long_string, max_chunk_size_bytes=50)
        self.assertEqual(len(chunks), 3)
        self.assertEqual("".join(chunks), long_string)

    def test_word_boundary_chunking(self):
        # Verify that text is chunked at space boundaries rather than cutting words in half
        from app.services.address_service import AddressService
        # "hello world" is 11 bytes. With chunk size 7, it should split at space ("hello ", "world")
        text = "hello world"
        chunks = AddressService.chunk_text(text, max_chunk_size_bytes=7)
        self.assertEqual(chunks, ["hello ", "world"])

    @patch("requests.post")
    def test_parallel_chunk_processing(self, mock_post):
        # Verify that process_file processes multiple chunks in parallel successfully
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "addresses": [
                {
                    "text": "123 Main St, New York, NY 10001",
                    "api_output": [
                        {
                            "components": {
                                "primary_number": "123",
                                "street_name": "Main",
                                "street_suffix": "St",
                                "city_name": "New York",
                                "state_abbreviation": "NY",
                                "zipcode": "10001"
                            }
                        }
                    ]
                }
            ]
        }
        mock_post.return_value = mock_response

        # Mocking chunk_text to produce 3 chunks
        from app.services.address_service import AddressService
        
        file_content = b"123 Main St, New York, NY 10001\n456 Main St, New York, NY 10001\n789 Main St, New York, NY 10001\n"
        files = {"file": ("test.txt", io.BytesIO(file_content), "text/plain")}
        
        # We override max_chunk_size_bytes to 32 to force 3 separate chunks
        original_chunk_text = AddressService.chunk_text
        def mock_chunk_text(text, max_chunk_size_bytes=60000):
            return original_chunk_text(text, max_chunk_size_bytes=32)

        with patch.object(AddressService, "chunk_text", side_effect=mock_chunk_text):
            response = self.client.post("/extract", files=files)
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertTrue(data["success"])
            # Parallel executor successfully collated all addresses
            self.assertEqual(data["count"], 3)

    @patch("requests.post")
    def test_fuzzy_matching_detects_typos(self, mock_post):
        # 1. Setup mock response returning the typo address "3900 Mian St"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "addresses": [
                {
                    "text": "3900 Mian St, Boston, MA 02201",
                    "api_output": [
                        {
                            "components": {
                                "primary_number": "3900",
                                "street_name": "Mian",
                                "street_suffix": "St",
                                "city_name": "Boston",
                                "state_abbreviation": "MA",
                                "zipcode": "02201"
                            }
                        }
                    ]
                }
            ]
        }
        mock_post.return_value = mock_response

        # 2. Insert the correct address "3900 Main St" manually into the clean test database
        from app.db import SessionLocal
        from app.models.database_models import Address as AddressRecord, DuplicateCandidate
        from sqlalchemy import select
        
        with SessionLocal() as session:
            correct_addr = AddressRecord(
                raw_text="3900 Main St, Boston, MA 02201",
                normalized="3900 MAIN ST BOSTON MA 02201",
                street="3900 MAIN ST",
                city="BOSTON",
                state="MA",
                zip="02201"
            )
            session.add(correct_addr)
            session.commit()

        # 3. Upload a file containing the typo
        file_content = b"3900 Mian St, Boston, MA 02201"
        files = {"file": ("letter_typo.txt", io.BytesIO(file_content), "text/plain")}
        
        response = self.client.post("/extract", files=files)
        self.assertEqual(response.status_code, 200)

        # 4. Verify that the pending duplicate candidate is created
        with SessionLocal() as session:
            candidates = session.scalars(select(DuplicateCandidate)).all()
            self.assertEqual(len(candidates), 1)
            self.assertEqual(candidates[0].status, "pending")
            self.assertGreaterEqual(candidates[0].score, 90)

    def test_merge_duplicates_repoints_documents_and_marks_loser_merged(self):
        # 1. Manually insert two addresses that are near duplicates
        from app.db import SessionLocal
        from app.models.database_models import Address as AddressRecord, DuplicateCandidate, Document, AddressDocument
        from sqlalchemy import select
        
        with SessionLocal() as session:
            # Create a document and link it to address_b (loser to be)
            doc1 = Document(
                filename="doc1.pdf",
                size_bytes=1024,
                sha256="abc123sha",
                status="processed",
                duplicate_addresses_caught=0
            )
            session.add(doc1)
            session.flush()

            # Create another document and link it to address_b
            doc2 = Document(
                filename="doc2.pdf",
                size_bytes=2048,
                sha256="xyz456sha",
                status="processed",
                duplicate_addresses_caught=0
            )
            session.add(doc2)
            session.flush()

            addr_a = AddressRecord(
                raw_text="123 Main St, New York, NY 10001",
                normalized="123 MAIN ST NEW YORK NY 10001",
                street="123 MAIN ST",
                city="NEW YORK",
                state="NY",
                zip="10001",
                review_status="unreviewed"
            )
            addr_b = AddressRecord(
                raw_text="123 Mian St, New York, NY 10001",
                normalized="123 MIAN ST NEW YORK NY 10001",
                street="123 MIAN ST",
                city="NEW YORK",
                state="NY",
                zip="10001",
                review_status="unreviewed"
            )
            session.add_all([addr_a, addr_b])
            session.flush()

            # Link address_b to doc1 and doc2
            link1 = AddressDocument(address_id=addr_b.id, document_id=doc1.id)
            link2 = AddressDocument(address_id=addr_b.id, document_id=doc2.id)
            # Link address_a to doc1 (so we test duplicate link prevention during merge)
            link3 = AddressDocument(address_id=addr_a.id, document_id=doc1.id)
            session.add_all([link1, link2, link3])
            session.flush()

            # Insert duplicate candidate
            candidate = DuplicateCandidate(
                address_a_id=addr_a.id,
                address_b_id=addr_b.id,
                score=95.0,
                status="pending"
            )
            session.add(candidate)
            session.commit()

            cand_id = candidate.id
            winner_id = addr_a.id
            loser_id = addr_b.id
            doc1_id = doc1.id
            doc2_id = doc2.id

        # 2. Check that GET /duplicates returns the candidate pair
        response = self.client.get("/duplicates")
        self.assertEqual(response.status_code, 200)
        duplicates = response.json()
        self.assertEqual(len(duplicates), 1)
        self.assertEqual(duplicates[0]["id"], cand_id)

        # 3. Resolve the duplicate by merging (keeping Address A)
        resolve_payload = {
            "action": "merge",
            "winning_address_id": winner_id
        }
        response = self.client.post(f"/duplicates/{cand_id}/resolve", json=resolve_payload)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])

        # 4. Verify DB state after merge
        with SessionLocal() as session:
            # Check candidate is deleted
            cand_check = session.get(DuplicateCandidate, cand_id)
            self.assertIsNone(cand_check)

            # Check winner status is verified
            winner_check = session.get(AddressRecord, winner_id)
            self.assertEqual(winner_check.review_status, "verified")

            # Check loser status is merged
            loser_check = session.get(AddressRecord, loser_id)
            self.assertEqual(loser_check.review_status, "merged")

            # Check document links are repointed:
            # doc1 should only have 1 link pointing to winner_id (the loser's link was deleted because winner was already linked)
            doc1_links = session.scalars(
                select(AddressDocument).where(AddressDocument.document_id == doc1_id)
            ).all()
            self.assertEqual(len(doc1_links), 1)
            self.assertEqual(doc1_links[0].address_id, winner_id)

            # doc2 should now have 1 link pointing to winner_id (repointed from loser_id)
            doc2_links = session.scalars(
                select(AddressDocument).where(AddressDocument.document_id == doc2_id)
            ).all()
            self.assertEqual(len(doc2_links), 1)
            self.assertEqual(doc2_links[0].address_id, winner_id)

        # 5. Check that GET /addresses does NOT list the merged address (loser_id)
        response = self.client.get("/addresses")
        self.assertEqual(response.status_code, 200)
        address_items = response.json()["items"]
        active_ids = [item["id"] for item in address_items]
        self.assertIn(winner_id, active_ids)
        self.assertNotIn(loser_id, active_ids)

    def test_patch_address_updates_fields_and_re_derives_normalized(self):
        from app.db import SessionLocal
        from app.models.database_models import Address as AddressRecord

        with SessionLocal() as session:
            addr = AddressRecord(
                raw_text="123 old street, old city, NY 10001",
                normalized="123 OLD STREET OLD CITY NY 10001",
                street="123 OLD STREET",
                city="OLD CITY",
                state="NY",
                zip="10001",
                review_status="needs_review"
            )
            session.add(addr)
            session.commit()
            addr_id = addr.id

        # Patch the street, city, state, zip
        patch_payload = {
            "street": "123 new ave",
            "city": "new city",
            "state": "NY",
            "zip": "10002",
            "review_status": "verified"
        }
        response = self.client.patch(f"/addresses/{addr_id}", json=patch_payload)
        self.assertEqual(response.status_code, 200)
        updated_data = response.json()
        
        # Verify the returned values
        self.assertEqual(updated_data["street"], "123 NEW AVE") # Should be uppercased
        self.assertEqual(updated_data["city"], "NEW CITY") # Should be uppercased
        self.assertEqual(updated_data["zip"], "10002")
        self.assertEqual(updated_data["review_status"], "verified")
        # Verify normalized is re-derived
        self.assertEqual(updated_data["normalized"], "123 NEW AVE NEW CITY NY 10002")

        # Verify DB reflects the change
        with SessionLocal() as session:
            db_addr = session.get(AddressRecord, addr_id)
            self.assertEqual(db_addr.street, "123 NEW AVE")
            self.assertEqual(db_addr.normalized, "123 NEW AVE NEW CITY NY 10002")

    def test_addresses_search_fts5(self):
        from app.db import SessionLocal
        from app.models.database_models import Address as AddressRecord

        with SessionLocal() as session:
            addr1 = AddressRecord(
                raw_text="3900 Main Street, Riverside, CA 92522",
                normalized="3900 MAIN ST RIVERSIDE CA 92522",
                street="3900 MAIN ST",
                city="RIVERSIDE",
                state="CA",
                zip="92522",
                review_status="unreviewed"
            )
            addr2 = AddressRecord(
                raw_text="100 Madison Ave, New York, NY 10016",
                normalized="100 MADISON AVE NEW YORK NY 10016",
                street="100 MADISON AVE",
                city="NEW YORK",
                state="NY",
                zip="10016",
                review_status="unreviewed"
            )
            session.add_all([addr1, addr2])
            session.commit()

        # Search for "River"
        response = self.client.get("/addresses?search=River")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["items"][0]["city"], "RIVERSIDE")

        # Search for "Madison"
        response = self.client.get("/addresses?search=Madison")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["items"][0]["city"], "NEW YORK")

    def test_addresses_export_csv(self):
        from app.db import SessionLocal
        from app.models.database_models import Address as AddressRecord

        with SessionLocal() as session:
            addr = AddressRecord(
                raw_text="3900 Main Street, Riverside, CA 92522",
                normalized="3900 MAIN ST RIVERSIDE CA 92522",
                street="3900 MAIN ST",
                city="RIVERSIDE",
                state="CA",
                zip="92522",
                review_status="unreviewed"
            )
            session.add(addr)
            session.commit()

        # Export CSV without filters
        response = self.client.get("/export?format=csv")
        self.assertEqual(response.status_code, 200)
        content = response.text
        self.assertIn("3900 MAIN ST RIVERSIDE CA 92522", content)
        self.assertIn("RIVERSIDE", content)

        # Export CSV with search filter matching "River"
        response = self.client.get("/export?format=csv&search=River")
        self.assertEqual(response.status_code, 200)
        content = response.text
        self.assertIn("3900 MAIN ST RIVERSIDE CA 92522", content)

        # Export CSV with search filter NOT matching
        response = self.client.get("/export?format=csv&search=Madison")
        self.assertEqual(response.status_code, 200)
        content = response.text
        self.assertNotIn("3900 MAIN ST RIVERSIDE CA 92522", content)

if __name__ == "__main__":
    unittest.main()
