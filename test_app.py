import unittest
from unittest.mock import patch, MagicMock
import io
import requests
from fastapi.testclient import TestClient
from fastapi import HTTPException

# Ensure environment variables are loaded
import os
os.environ["SMARTY_AUTH_ID"] = "test-id"
os.environ["SMARTY_AUTH_TOKEN"] = "test-token"

from main import app
from app.services.file_parser import FileParser

class TestAddressExtractionApp(unittest.TestCase):
    def setUp(self):
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

if __name__ == "__main__":
    unittest.main()
