from reducto import Reducto
from typing import Dict, Any, List, Optional
from app.core.config import settings
from app.core.exceptions import ReductoError, FileUploadError
import logging
import os
import asyncio

logger = logging.getLogger(__name__)


class ReductoService:
    """
    Service for interacting with Reducto API for document parsing and extraction.

    Reducto provides document parsing with confidence scores (logprobs_confidence)
    for each extracted chunk. This service handles both unstructured parsing and
    schema-based structured extraction.
    """

    def __init__(self):
        self.api_key = settings.REDUCTO_API_KEY
        self.timeout = settings.REDUCTO_TIMEOUT
        # Reducto SDK requires API key to be passed
        self.client = Reducto(api_key=self.api_key)
        logger.debug(f"ReductoService initialized")

    async def parse_document(self, file_path: str) -> Dict[str, Any]:
        """
        Parse a document using Reducto API.

        This performs unstructured parsing, extracting all text chunks with
        confidence scores for each chunk.

        Args:
            file_path: Path to the document file to parse

        Returns:
            {
                "result": {
                    "chunks": [...],
                    "metadata": {...}
                },
                "confidence_scores": {...}
            }

        Raises:
            FileUploadError: If the file cannot be read or is invalid
            ReductoError: If the Reducto API call fails
        """
        if not os.path.exists(file_path):
            raise FileUploadError(f"File not found: {file_path}")

        file_size = os.path.getsize(file_path)
        logger.info(f"Parsing document: {file_path} (size: {file_size} bytes)")

        try:
            # Use Reducto SDK to parse document (run in thread pool since SDK is sync)
            # Step 1: Upload the file
            def upload_file():
                with open(file_path, "rb") as f:
                    return self.client.upload(file=f)

            upload_response = await asyncio.to_thread(upload_file)

            # Step 2: Parse using the uploaded file ID
            parse_response = await asyncio.to_thread(
                self.client.parse.run,
                document_url=upload_response.file_id
            )

            # Get result from response and convert Pydantic objects to dict
            result = parse_response.result if hasattr(parse_response, 'result') else parse_response

            # Convert Pydantic objects to dict
            if hasattr(result, 'model_dump'):
                result = result.model_dump()
            elif hasattr(result, 'dict'):
                result = result.dict()
            elif not isinstance(result, dict):
                result = dict(result) if hasattr(result, '__iter__') else {"data": str(result)}

            # Extract confidence scores from chunks
            confidence_scores = self._extract_confidence_scores(result)

            num_chunks = len(result.get("chunks", [])) if isinstance(result, dict) else 0
            avg_confidence = sum(confidence_scores.values()) / len(confidence_scores) if confidence_scores else 0

            logger.info(
                f"Document parsed successfully: {file_path} - "
                f"{num_chunks} chunks, avg confidence: {avg_confidence:.3f}"
            )

            return {
                "result": result,
                "confidence_scores": confidence_scores,
                "job_id": parse_response.job_id if hasattr(parse_response, 'job_id') else None
            }
        except ConnectionError as e:
            logger.error(f"Cannot connect to Reducto API: {str(e)}")
            raise ReductoError("Reducto API is unavailable. Please check your API key and internet connection.", e)
        except Exception as e:
            logger.error(f"Unexpected error parsing {file_path}: {str(e)}", exc_info=True)
            raise ReductoError(f"Reducto API error: {str(e)}", e)

    async def extract_structured(
        self,
        schema: Dict[str, Any],
        file_path: str = None,
        job_id: str = None
    ) -> Dict[str, Any]:
        """
        Extract structured data from document using schema.

        This performs schema-based extraction using Reducto's pipelining feature.
        Can accept either a file_path (will upload) or job_id (from previous parse).

        PIPELINING: Use job_id from parse_document() to avoid re-uploading/re-parsing.
        This reduces costs by ~50% and improves latency.

        Args:
            schema: Extraction schema with fields and hints
            file_path: Path to document (if not using job_id)
            job_id: Job ID from previous parse (preferred - uses jobid:// pipeline)

        Returns:
            {
                "extractions": {
                    "field_name": {
                        "value": "...",
                        "confidence": 0.85,
                        "source_page": 1,
                        "source_bbox": [x, y, width, height]
                    }
                },
                "job_id": "..."
            }

        Raises:
            FileUploadError: If neither file_path nor job_id provided
            ReductoError: If the Reducto API call fails
        """
        if not file_path and not job_id:
            raise FileUploadError("Must provide either file_path or job_id")

        num_fields = len(schema.get("fields", schema.get("properties", {}).keys()))

        try:
            # PIPELINE OPTIMIZATION: Use jobid:// if we have a parse job_id
            if job_id:
                logger.info(f"Extracting {num_fields} fields using pipeline (jobid://{job_id})")
                document_url = f"jobid://{job_id}"
            else:
                # Fallback: Upload file if no job_id provided
                logger.info(f"Extracting {num_fields} fields from: {file_path}")
                if not os.path.exists(file_path):
                    raise FileUploadError(f"File not found: {file_path}")

                def upload_file():
                    with open(file_path, "rb") as f:
                        return self.client.upload(file=f)

                upload_response = await asyncio.to_thread(upload_file)
                document_url = upload_response.file_id

            # Extract using the document URL (either jobid:// or file_id)
            extract_response = await asyncio.to_thread(
                self.client.extract.run,
                document_url=document_url,
                schema=schema
            )

            result = extract_response.result if hasattr(extract_response, 'result') else extract_response
            raw_extractions = result if isinstance(result, list) else result.get("extractions", {})

            # Parse extractions to include bbox and page information
            extractions = self._parse_extraction_with_bbox(raw_extractions)

            logger.info(
                f"Structured extraction completed - "
                f"{len(extractions) if isinstance(extractions, (list, dict)) else 0}/{num_fields} fields extracted"
            )

            return {
                "extractions": extractions,
                "job_id": extract_response.job_id if hasattr(extract_response, 'job_id') else None
            }
        except Exception as e:
            error_msg = str(e)
            # Check if job_id is expired/not found
            if job_id and ("job not found" in error_msg.lower() or "parse job not found" in error_msg.lower()):
                logger.warning(f"Job ID {job_id} expired or not found")
                raise ReductoError(f"Job ID expired or not found: {job_id}", e)
            logger.error(f"Unexpected error extracting: {error_msg}", exc_info=True)
            raise ReductoError(f"Reducto extraction error: {error_msg}", e)

    async def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Get status of async processing job"""
        try:
            # Note: The SDK might have a method for this, but for now return a simple status
            return {
                "job_id": job_id,
                "status": "completed"
            }
        except Exception as e:
            logger.error(f"Error getting job status: {str(e)}")
            raise ReductoError(f"Failed to get job status: {str(e)}", e)

    def _extract_confidence_scores(self, result: Dict[str, Any]) -> Dict[str, float]:
        """Extract confidence scores from Reducto response blocks"""
        confidence_scores = {}

        if "chunks" in result:
            for chunk in result["chunks"]:
                if "logprobs_confidence" in chunk:
                    chunk_id = chunk.get("id", len(confidence_scores))
                    confidence_scores[chunk_id] = chunk["logprobs_confidence"]

        return confidence_scores

    def get_confidence_label(self, score: float) -> str:
        """
        Convert confidence score to label (High/Medium/Low)

        Note: These thresholds are hardcoded for display purposes only.
        They do not affect business logic (which uses review_threshold setting).
        """
        if score >= 0.8:
            return "High"
        elif score >= 0.6:
            return "Medium"
        else:
            return "Low"

    def extract_field_from_chunks(
        self,
        chunks: List[Dict[str, Any]],
        hints: List[str]
    ) -> Optional[Dict[str, Any]]:
        """
        Extract field value from chunks using extraction hints

        Args:
            chunks: List of document chunks
            hints: Extraction hints (keywords to look for)

        Returns:
            {
                "value": "...",
                "confidence": 0.85,
                "chunk_id": "...",
                "page": 1
            }
        """
        for chunk in chunks:
            # Reducto uses 'content' field for text
            text = chunk.get("content", chunk.get("text", ""))

            # Check if any hint matches in the chunk
            for hint in hints:
                if hint.lower() in text.lower():
                    return {
                        "value": self._extract_value_after_hint(text, hint),
                        "confidence": chunk.get("logprobs_confidence", 0.0),
                        "chunk_id": chunk.get("id"),
                        "page": chunk.get("page", 1)
                    }

        return None

    def _extract_value_after_hint(self, text: str, hint: str) -> str:
        """Extract value that appears after the hint in text"""
        # Simple extraction: get text after hint until newline or period
        hint_pos = text.lower().find(hint.lower())
        if hint_pos == -1:
            return ""

        start = hint_pos + len(hint)
        # Skip whitespace and colon
        while start < len(text) and text[start] in " :\t":
            start += 1

        # Find end (newline or period)
        end = start
        while end < len(text) and text[end] not in "\n.":
            end += 1

        return text[start:end].strip()

    def _parse_extraction_with_bbox(self, raw_extractions: Any) -> Dict[str, Any]:
        """
        Parse Reducto extraction response to include bbox and page information.

        Reducto returns extractions in various formats:
        - List of dicts with 'field', 'value', 'bbox', 'page', 'confidence'
        - Dict with field names as keys

        Args:
            raw_extractions: Raw extraction response from Reducto

        Returns:
            Dict with normalized structure:
            {
                "field_name": {
                    "value": "...",
                    "confidence": 0.85,
                    "source_page": 1,
                    "source_bbox": [x, y, width, height]
                }
            }
        """
        parsed = {}

        # Handle list format (array of extraction objects)
        if isinstance(raw_extractions, list):
            for extraction in raw_extractions:
                if not isinstance(extraction, dict):
                    continue

                field_name = extraction.get("field", extraction.get("name"))
                if not field_name:
                    continue

                # Extract value (may be nested)
                value = extraction.get("value", extraction.get("content", ""))

                # Get confidence (various field names)
                confidence = extraction.get("confidence",
                                          extraction.get("score",
                                          extraction.get("logprobs_confidence", 0.85)))

                # Get bbox coordinates
                bbox = extraction.get("bbox", extraction.get("bounding_box"))

                # Get page number
                page = extraction.get("page", extraction.get("page_number", 1))

                parsed[field_name] = {
                    "value": str(value) if value is not None else "",
                    "confidence": float(confidence) if confidence is not None else 0.85,
                    "source_page": int(page) if page is not None else None,
                    "source_bbox": bbox if bbox else None
                }

        # Handle dict format (field_name: data)
        elif isinstance(raw_extractions, dict):
            for field_name, field_data in raw_extractions.items():
                # Check if already structured
                if isinstance(field_data, dict):
                    value = field_data.get("value", field_data.get("content", ""))
                    confidence = field_data.get("confidence",
                                              field_data.get("score",
                                              field_data.get("logprobs_confidence", 0.85)))
                    bbox = field_data.get("bbox", field_data.get("bounding_box"))
                    page = field_data.get("page", field_data.get("page_number", 1))
                else:
                    # Simple value format
                    value = field_data
                    confidence = 0.85
                    bbox = None
                    page = None

                parsed[field_name] = {
                    "value": str(value) if value is not None else "",
                    "confidence": float(confidence) if confidence is not None else 0.85,
                    "source_page": int(page) if page is not None else None,
                    "source_bbox": bbox if bbox else None
                }

        return parsed

