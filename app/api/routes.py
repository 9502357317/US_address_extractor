from fastapi import APIRouter, UploadFile, HTTPException, File
from fastapi.responses import JSONResponse
from app.services.address_service import AddressService

router = APIRouter()

class ExtractController:
    @staticmethod
    def format_response(addresses: list) -> dict:
        """
        Format successful address extraction results to match API contract.
        """
        return {
            "success": True,
            "count": len(addresses),
            "addresses": [
                {
                    "input_text": addr.input_text,
                    "components": {
                        "primary_number": addr.components.primary_number,
                        "street_name": addr.components.street_name,
                        "street_suffix": addr.components.street_suffix,
                        "city_name": addr.components.city_name,
                        "state_abbreviation": addr.components.state_abbreviation,
                        "zipcode": addr.components.zipcode
                    }
                } for addr in addresses
            ]
        }

    @staticmethod
    def format_error(exception: Exception) -> dict:
        """
        Format error response to hide internal stack traces and provide user-friendly messages.
        """
        if isinstance(exception, HTTPException):
            return {
                "success": False,
                "error": exception.detail
            }
        return {
            "success": False,
            "error": "Something went wrong on server. Please try again later."
        }

    @staticmethod
    def extract(request: UploadFile) -> JSONResponse:
        """
        Receives UploadFile, processes it through AddressService, and formats the response.
        """
        try:
            addresses = AddressService.process_file(request)
            return JSONResponse(
                status_code=200,
                content=ExtractController.format_response(addresses)
            )
        except HTTPException as e:
            return JSONResponse(
                status_code=e.status_code,
                content=ExtractController.format_error(e)
            )
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content=ExtractController.format_error(e)
            )

@router.post("/extract")
async def extract_endpoint(file: UploadFile = File(...)):
    """
    POST /extract endpoint accepting PDF/TXT files in multipart/form-data.
    """
    return ExtractController.extract(file)
