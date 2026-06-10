import logging

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.services.address_service import AddressService
from app.services.database_service import DatabaseService
import csv
import io
from fastapi.responses import StreamingResponse


router = APIRouter()
logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Pydantic Schemas for Request Validation
# -----------------------------------------------------------------------------

class AddressPatch(BaseModel):
    """Schema for patching specific fields of an address."""
    street: str | None = None
    city: str | None = None
    state: str | None = None
    zip: str | None = None
    review_status: str | None = None


class ResolveDuplicate(BaseModel):
    """Schema for resolving duplicate candidates."""
    action: str  # Must be "merge" or "not_duplicate"
    winning_address_id: int | None = None  # Required only when action is "merge"


class ExtractController:
    @staticmethod
    def format_response(
        addresses: list,
        document_id: int,
        address_results: list[dict],
    ) -> dict:
        """
        Build the upload response.

        address_results comes from DatabaseService.save_extracted_addresses()
        and tells us whether each normalized address was inserted as new or
        reused from an existing address row.
        """

        new_address_count = sum(
            1 for item in address_results if item["is_new"]
        )
        existing_address_count = sum(
            1 for item in address_results if not item["is_new"]
        )

        return {
            "success": True,
            "document_id": document_id,
            "address_ids": [
                item["id"]
                for item in address_results
            ],
            "count": len(addresses),
            "new_address_count": new_address_count,
            "existing_address_count": existing_address_count,
            "addresses": [
                {
                    "id": address_results[index]["id"],
                    "is_new": address_results[index]["is_new"],
                    "dedupe_status": (
                        "new"
                        if address_results[index]["is_new"]
                        else "existing"
                    ),
                    "input_text": address.input_text,
                    "components": {
                        "primary_number": address.components.primary_number,
                        "street_name": address.components.street_name,
                        "street_suffix": address.components.street_suffix,
                        "city_name": address.components.city_name,
                        "state_abbreviation": (
                            address.components.state_abbreviation
                        ),
                        "zipcode": address.components.zipcode,
                    },
                }
                for index, address in enumerate(addresses)
            ],
        }

    @staticmethod
    def extract(request: UploadFile) -> JSONResponse:
        """
        Handle one uploaded file.

        Flow:
        1. Hash the uploaded bytes.
        2. Reject duplicate files by SHA-256.
        3. Parse the file text and validate.
        4. Reject content-level duplicates (same normalized text hash).
        5. Create a document row before extraction.
        6. Extract addresses from parsed text.
        7. Save only new normalized addresses and link existing ones.
        8. Return which addresses were new vs already known.
        """

        file_details = DatabaseService.get_file_details(request)

        # 1. Byte-level duplicate check (SHA-256)
        existing = DatabaseService.get_document_by_sha256(
            file_details["sha256"]
        )

        if existing:
            # Duplicate files do not create new document rows.
            # Store an upload event so /stats can count rejected duplicates.
            DatabaseService.record_duplicate_file_rejected(
                file_details=file_details,
                existing_document_id=existing.id,
            )

            logger.warning(
                "Duplicate upload rejected: filename=%s existing_id=%s",
                file_details["filename"],
                existing.id,
            )

            return JSONResponse(
                status_code=409,
                content={
                    "success": False,
                    "error": "This file has already been uploaded.",
                    "existing_document_id": existing.id,
                    "uploaded_at": existing.uploaded_at.isoformat(),
                },
            )

        # 2. Extract text and validate early
        from app.services.file_validator import FileValidator
        from app.services.file_parser import FileParser
        import re
        import hashlib

        try:
            FileValidator.validate_file_type(request)
            FileValidator.validate_file_size(request)
            text = FileParser.read_file(request)
            FileValidator.validate_empty_file(text)

            if len(text.encode("utf-8")) > 10 * 1024 * 1024:
                raise HTTPException(
                    status_code=400,
                    detail="The file is too large to process. Please upload a smaller document."
                )

            # Compute content-level hash: lowercase and collapse whitespace
            text_lowercased = text.lower()
            collapsed = re.sub(r'\s+', ' ', text_lowercased).strip()
            content_hash = hashlib.sha256(collapsed.encode("utf-8")).hexdigest()

            # Check for content-level duplicate
            existing_content = DatabaseService.get_document_by_content_hash(content_hash)
            if existing_content:
                DatabaseService.record_duplicate_file_rejected(
                    file_details=file_details,
                    existing_document_id=existing_content.id,
                )

                logger.warning(
                    "Duplicate content upload rejected: filename=%s existing_id=%s",
                    file_details["filename"],
                    existing_content.id,
                )

                return JSONResponse(
                    status_code=409,
                    content={
                        "success": False,
                        "error": "This file has already been uploaded.",
                        "existing_document_id": existing_content.id,
                        "uploaded_at": existing_content.uploaded_at.isoformat(),
                    },
                )

        except HTTPException as error:
            # Since validation failed before create_document, we return directly
            return JSONResponse(
                status_code=error.status_code,
                content={
                    "success": False,
                    "error": error.detail,
                },
            )
        except Exception:
            logger.exception("Unexpected error during pre-validation")
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "error": "Something went wrong on server. Please try again later.",
                },
            )

        # 3. Create document row in registry database
        document_id = DatabaseService.create_document(file_details)

        try:
            # Process the pre-parsed text directly
            addresses = AddressService.process_text(text)

            address_results = DatabaseService.save_extracted_addresses(
                document_id=document_id,
                extracted_addresses=addresses,
                content_hash=content_hash,
            )

            logger.info(
                "Document processed: document_id=%s filename=%s",
                document_id,
                file_details["filename"],
            )

            return JSONResponse(
                status_code=200,
                content=ExtractController.format_response(
                    addresses=addresses,
                    document_id=document_id,
                    address_results=address_results,
                ),
            )

        except HTTPException as error:
            DatabaseService.mark_document_failed(
                document_id=document_id,
                reason=str(error.detail),
            )

            logger.warning(
                "Document extraction failed: document_id=%s reason=%s",
                document_id,
                error.detail,
            )

            return JSONResponse(
                status_code=error.status_code,
                content={
                    "success": False,
                    "document_id": document_id,
                    "error": error.detail,
                },
            )

        except Exception:
            DatabaseService.mark_document_failed(
                document_id=document_id,
                reason="Unexpected server error during extraction.",
            )

            logger.exception(
                "Unexpected extraction failure: document_id=%s",
                document_id,
            )

            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "document_id": document_id,
                    "error": (
                        "Something went wrong on server. "
                        "Please try again later."
                    ),
                },
            )


@router.post("/extract")
async def extract_endpoint(file: UploadFile = File(...)):
    """Upload one file and extract/deduplicate addresses."""

    return ExtractController.extract(file)


@router.get("/documents")
def list_documents(status: str | None = None):
    """List documents, optionally filtered by processed or failed status."""

    if status not in (None, "processed", "failed"):
        raise HTTPException(
            status_code=400,
            detail="Status must be processed or failed.",
        )

    return DatabaseService.list_documents(status)


@router.get("/documents/{document_id}")
def get_document(document_id: int):
    """Return one document with linked extracted addresses."""

    document = DatabaseService.get_document(document_id)

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    return document


@router.get("/addresses")
def list_addresses(
    limit: int = 20,
    offset: int = 0,
    search: str | None = None,
    city: str | None = None,
    state: str | None = None,
    zip: str | None = None,
):
    """
    Return a paginated list of active addresses with optional filters.

    Soft-deleted addresses are excluded by DatabaseService.list_addresses().
    Filters combine with AND logic.
    """

    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=400,
            detail="Limit must be between 1 and 100.",
        )

    if offset < 0:
        raise HTTPException(
            status_code=400,
            detail="Offset must be 0 or greater.",
        )

    return DatabaseService.list_addresses(
        limit=limit,
        offset=offset,
        search=search,
        city=city,
        state=state,
        zip=zip,
    )


@router.get("/addresses/filter-options")
def get_filter_options():
    """Return all unique cities, states, and zips in the registry for filters."""
    return DatabaseService.get_filter_options()


# -----------------------------------------------------------------------------
# Human Review & Merge APIs
# -----------------------------------------------------------------------------

@router.patch("/addresses/{address_id}")
def patch_address(address_id: int, patch_data: AddressPatch):
    """
    Let a reviewer correct specific fields of an address.
    The normalized string is re-derived automatically after the edit.
    """
    address = DatabaseService.patch_address(
        address_id=address_id,
        data=patch_data.model_dump(exclude_unset=True)
    )
    if address is None:
        raise HTTPException(
            status_code=404,
            detail="Address not found."
        )
    return address


@router.get("/duplicates")
def list_duplicates():
    """
    List all pending duplicate candidates to show in the human review queue.
    """
    return DatabaseService.list_duplicates()


@router.post("/duplicates/{duplicate_id}/resolve")
def resolve_duplicate(duplicate_id: int, resolve_data: ResolveDuplicate):
    """
    Resolve a duplicate candidate pair by:
    - 'merge': repoint losing document links, verify winner, and mark loser merged.
    - 'not_duplicate': dismiss candidate link.
    """
    if resolve_data.action not in ("merge", "not_duplicate"):
        raise HTTPException(
            status_code=400,
            detail="Action must be merge or not_duplicate."
        )
    
    if resolve_data.action == "merge" and not resolve_data.winning_address_id:
        raise HTTPException(
            status_code=400,
            detail="winning_address_id is required for merge action."
        )

    success = DatabaseService.resolve_duplicate(
        duplicate_id=duplicate_id,
        action=resolve_data.action,
        winning_address_id=resolve_data.winning_address_id
    )
    
    if not success:
        raise HTTPException(
            status_code=404,
            detail="Duplicate candidate not found or invalid winning address."
        )
        
    return {"success": True, "message": f"Duplicate candidate resolved."}


@router.get("/addresses/{address_id}")
def get_address(address_id: int):
    """
    Return one address with every document where it appeared.

    This is the detail view for the address registry.
    """

    address = DatabaseService.get_address(address_id)

    if address is None:
        raise HTTPException(
            status_code=404,
            detail="Address not found.",
        )

    return address


@router.delete("/addresses/{address_id}")
def delete_address(address_id: int):
    """
    Soft-delete one address.

    The row stays in SQLite, but deleted_at is set and it disappears from
    normal /addresses list results.
    """

    deleted = DatabaseService.soft_delete_address(address_id)

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Address not found.",
        )

    return {
        "success": True,
        "address_id": address_id,
        "message": "Address soft-deleted.",
    }


@router.get("/stats")
def get_stats():
    """Return task 5 summary counts."""

    return DatabaseService.get_stats()

@router.get("/export")
def export_addresses(
    format: str = "csv",
    search: str | None = None,
    city: str | None = None,
    state: str | None = None,
    zip: str | None = None,
):
    """
    Streams all active (not deleted, not merged) addresses matching the filters 
    as a CSV download.
    """
    if format != "csv":
        raise HTTPException(
            status_code=400,
            detail="Unsupported export format. Only 'csv' is supported."
        )

    def generate_csv_rows():
        # Initialize StringIO to format each CSV row
        output = io.StringIO()
        writer = csv.writer(output)
        
        # 1. Write the Header Row
        writer.writerow([
            "id", "raw_text", "normalized", "street", "city", "state", "zip", "review_status", "created_at"
        ])
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)

        # 2. Import DB dependencies inside the generator to avoid circular imports
        from app.db import SessionLocal
        from app.models.database_models import Address as AddressRecord
        from sqlalchemy import select, or_, text

        with SessionLocal() as session:
            # Respecting "live" addresses (not deleted, review_status not merged)
            filters = [
                AddressRecord.deleted_at.is_(None),
                or_(AddressRecord.review_status != "merged", AddressRecord.review_status.is_(None))
            ]

            # Apply active search/filter options
            if search:
                words = [w.strip() for w in search.strip().split() if w.strip()]
                if words:
                    escaped_words = [w.replace('"', '""') for w in words]
                    fts_query = " ".join(f'"{ew}"*' for ew in escaped_words)
                    fts_subquery = (
                        select(text("address_id"))
                        .select_from(text("addresses_fts"))
                        .where(text("addresses_fts MATCH :query").bindparams(query=fts_query))
                    )
                    filters.append(AddressRecord.id.in_(fts_subquery))

            if city:
                filters.append(AddressRecord.city == city.strip().upper())

            if state:
                filters.append(AddressRecord.state == state.strip().upper())

            if zip:
                filters.append(AddressRecord.zip == zip.strip())

            # Fetch matching addresses ordered by creation date
            statement = (
                select(AddressRecord)
                .where(*filters)
                .order_by(AddressRecord.created_at.desc())
            )
            addresses = session.scalars(statement).all()

            # Yield each row formatted as CSV
            for address in addresses:
                writer.writerow([
                    address.id,
                    address.raw_text,
                    address.normalized,
                    address.street,
                    address.city,
                    address.state,
                    address.zip,
                    address.review_status,
                    address.created_at.isoformat() if address.created_at else ""
                ])
                yield output.getvalue()
                output.seek(0)
                output.truncate(0)

    # Return StreamingResponse with CSV content type
    return StreamingResponse(
        generate_csv_rows(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=exported_addresses.csv"}
    )
