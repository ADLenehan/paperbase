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

            # DEBUG: Log first chunk structure to understand data format
            if num_chunks > 0 and isinstance(result, dict):
                first_chunk = result.get("chunks", [])[0]
                logger.debug(f"First chunk keys: {list(first_chunk.keys())}")
                logger.debug(f"First chunk content sample: {str(first_chunk)[:300]}")

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
            schema: Extraction schema with fields and hints (supports complex types)
            file_path: Path to document (if not using job_id)
            job_id: Job ID from previous parse (preferred - uses jobid:// pipeline)

        Returns:
            {
                "extractions": {
                    "field_name": {
                        "value": "..." | [...] | {...},  # Supports complex types
                        "confidence": 0.85,
                        "source_page": 1,
                        "source_bbox": [x, y, width, height],
                        "field_type": "text|array|table|array_of_objects"
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

        # Convert our schema format to Reducto's JSON Schema format
        reducto_schema = self._convert_to_reducto_schema(schema)
        num_fields = len(schema.get("fields", []))

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

            # Determine if we need array extraction mode for tables/long lists
            has_tables = any(f.get("type") == "table" for f in schema.get("fields", []))
            has_arrays = any(f.get("type") in ["array", "array_of_objects"] for f in schema.get("fields", []))

            # Extract using the document URL with appropriate settings
            logger.info(f"Calling Reducto extract API with {num_fields} fields (tables={has_tables}, arrays={has_arrays})")

            # Build extract parameters for Reducto SDK v0.11.0
            # Required: document_url, schema
            # Optional: system_prompt, array_extract
            # Note: Citations are enabled by default in recent SDK versions
            extract_kwargs = {
                "document_url": document_url,
                "schema": reducto_schema,
                "system_prompt": "Be precise and thorough. Extract all data maintaining structure and format."
            }

            # Enable array extraction for tables and arrays
            if has_tables or has_arrays:
                extract_kwargs["array_extract"] = {
                    "enabled": True,
                    "mode": "auto"
                }

            extract_response = await asyncio.to_thread(
                self.client.extract.run,
                **extract_kwargs
            )

            logger.info(f"Reducto response type: {type(extract_response)}")

            result = extract_response.result if hasattr(extract_response, 'result') else extract_response
            logger.info(f"Result type: {type(result)}")

            raw_extractions = result if isinstance(result, list) else result.get("extractions", result)
            logger.info(f"Raw extractions type: {type(raw_extractions)}, Length: {len(raw_extractions) if isinstance(raw_extractions, (list, dict)) else 0}")

            # Parse citations to get confidence scores and bbox data
            citations_data = {}

            # DEBUG: Check citation availability
            has_citations_attr = hasattr(extract_response, 'citations')
            citations_value = extract_response.citations if has_citations_attr else None
            logger.info(f"Citations check: has_attr={has_citations_attr}, is_none={citations_value is None}, type={type(citations_value)}")

            if has_citations_attr and citations_value:
                # DEBUG: Log raw citations structure
                if isinstance(citations_value, list):
                    logger.info(f"Citations list length: {len(citations_value)}")
                    if len(citations_value) > 0:
                        logger.debug(f"First citation sample: {str(citations_value[0])[:500]}")

                citations_data = self._parse_citations(citations_value)
                logger.info(f"Parsed {len(citations_data)} citations with confidence scores and bbox data")

                # DEBUG: Log fields with/without bbox
                fields_with_bbox = [f for f, c in citations_data.items() if c.get('bbox')]
                fields_without_bbox = [f for f, c in citations_data.items() if not c.get('bbox')]
                logger.info(f"Citations with bbox: {len(fields_with_bbox)}, without bbox: {len(fields_without_bbox)}")
                if fields_without_bbox:
                    logger.warning(f"Fields missing bbox: {fields_without_bbox[:5]}")
            else:
                logger.warning("No citations returned from Reducto API despite generate_citations=True")

            # Parse extractions to include bbox, page, and type information
            extractions = self._parse_extraction_with_complex_types(raw_extractions, schema, citations_data)

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
            logger.info(f"Parsing list with {len(raw_extractions)} items")
            for idx, extraction in enumerate(raw_extractions):
                logger.info(f"Item {idx}: type={type(extraction)}, keys={extraction.keys() if isinstance(extraction, dict) else 'N/A'}")
                if not isinstance(extraction, dict):
                    continue

                # Check if this is a dict with field names as keys (Reducto format)
                field_name = extraction.get("field", extraction.get("name"))
                if not field_name:
                    # This is a dict like {"style_number": "...", "season": "..."}
                    # Parse it as field dict (the actual extracted data!)
                    logger.info(f"List item {idx} has no 'field' or 'name' key - this IS the field data dict")
                    # Recursively call this function with the dict
                    parsed_dict = self._parse_extraction_with_bbox(extraction)
                    logger.info(f"Parsed {len(parsed_dict)} fields from embedded dict")
                    return parsed_dict  # Return immediately - this is the actual data

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
            logger.info(f"Parsing dict with {len(raw_extractions)} fields")
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
                    # Simple value format: "field_name": "value"
                    value = field_data
                    confidence = 0.85
                    bbox = None
                    page = None

                logger.debug(f"  {field_name}: value='{value}', confidence={confidence}")
                parsed[field_name] = {
                    "value": str(value) if value is not None else "",
                    "confidence": float(confidence) if confidence is not None else 0.85,
                    "source_page": int(page) if page is not None else None,
                    "source_bbox": bbox if bbox else None
                }

            logger.info(f"Dict parsing complete: {len(parsed)} fields with values")

        return parsed

    def _convert_to_reducto_schema(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert our schema format to Reducto's JSON Schema format.

        Handles complex types: array, table, array_of_objects

        Args:
            schema: Our schema with fields list

        Returns:
            Reducto-compatible JSON Schema
        """
        def map_type_to_json_schema(field_type: str) -> str:
            """Map our internal types to JSON Schema types."""
            type_map = {
                "text": "string",
                "number": "number",
                "boolean": "boolean",
                "date": "string",  # Use string with format
            }
            return type_map.get(field_type, "string")

        reducto_schema = {
            "type": "object",
            "properties": {},
            "required": []
        }

        for field in schema.get("fields", []):
            field_name = field["name"]
            field_type = field.get("type", "text")
            required = field.get("required", False)

            if required:
                reducto_schema["required"].append(field_name)

            # Map our types to JSON Schema types
            if field_type == "text":
                reducto_schema["properties"][field_name] = {
                    "type": "string",
                    "description": " ".join(field.get("extraction_hints", []))
                }
            elif field_type == "number":
                reducto_schema["properties"][field_name] = {
                    "type": "number",
                    "description": " ".join(field.get("extraction_hints", []))
                }
            elif field_type == "boolean":
                reducto_schema["properties"][field_name] = {
                    "type": "boolean",
                    "description": " ".join(field.get("extraction_hints", []))
                }
            elif field_type == "date":
                reducto_schema["properties"][field_name] = {
                    "type": "string",
                    "format": "date",
                    "description": " ".join(field.get("extraction_hints", []))
                }
            elif field_type == "array":
                # Simple array (list of strings or numbers)
                item_type = field.get("item_type", "text")  # Get our internal type
                json_item_type = map_type_to_json_schema(item_type)  # Convert to JSON Schema type
                reducto_schema["properties"][field_name] = {
                    "type": "array",
                    "items": {"type": json_item_type},
                    "description": " ".join(field.get("extraction_hints", []))
                }
            elif field_type == "array_of_objects":
                # Array of structured objects (e.g., invoice line items)
                object_schema = field.get("object_schema", {})
                properties = {}
                for obj_field_name, obj_field_def in object_schema.items():
                    obj_type = obj_field_def.get("type", "text")
                    json_obj_type = map_type_to_json_schema(obj_type)
                    properties[obj_field_name] = {"type": json_obj_type}

                reducto_schema["properties"][field_name] = {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": properties
                    },
                    "description": " ".join(field.get("extraction_hints", []))
                }
            elif field_type == "table":
                # Table with dynamic columns (e.g., grading specs)
                table_schema = field.get("table_schema", {})
                row_identifier = table_schema.get("row_identifier", "id")
                columns = table_schema.get("columns", [])
                value_type = table_schema.get("value_type", "text")
                json_value_type = map_type_to_json_schema(value_type)

                # Build table as array of objects
                properties = {row_identifier: {"type": "string"}}
                for col in columns:
                    properties[col] = {"type": json_value_type}

                reducto_schema["properties"][field_name] = {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": properties
                    },
                    "description": " ".join(field.get("extraction_hints", []))
                }

        return reducto_schema

    def _parse_citations(self, citations: Any) -> Dict[str, Dict[str, Any]]:
        """
        Parse Reducto citations to extract confidence scores and bbox data.

        Args:
            citations: Citations array from Reducto extract response

        Returns:
            Dict mapping field names to their citation metadata:
            {
                "field_name": {
                    "confidence": 0.96,
                    "bbox": {...},
                    "page": 2
                }
            }
        """
        parsed_citations = {}

        # Handle Pydantic model
        if hasattr(citations, 'model_dump'):
            citations = citations.model_dump()
        elif hasattr(citations, 'dict'):
            citations = citations.dict()

        # Citations format: [{"field_name": [{"content": "...", "bbox": {...}, "confidence": "high", ...}]}]
        if isinstance(citations, list) and citations:
            for citation_obj in citations:
                if isinstance(citation_obj, dict):
                    for field_name, citation_list in citation_obj.items():
                        if isinstance(citation_list, list) and citation_list:
                            # Get first citation for this field
                            first_citation = citation_list[0]

                            # Handle case where citation might not be a dict (e.g., nested arrays)
                            if not isinstance(first_citation, dict):
                                continue

                            # Extract confidence (use parse_confidence if available)
                            granular_conf = first_citation.get("granular_confidence", {}) or {}
                            confidence = None
                            if isinstance(granular_conf, dict):
                                confidence = granular_conf.get("parse_confidence")

                            # Fallback to categorical confidence if no numeric available
                            if confidence is None:
                                cat_conf = first_citation.get("confidence", "high")
                                confidence = {"high": 0.9, "medium": 0.7, "low": 0.5}.get(cat_conf, 0.85)

                            # Extract bbox and page
                            bbox = first_citation.get("bbox", {})

                            # DEBUG: Log bbox extraction
                            has_bbox = bool(bbox and isinstance(bbox, dict))
                            if has_bbox:
                                bbox_keys = list(bbox.keys()) if isinstance(bbox, dict) else []
                                has_coords = all(k in bbox for k in ['left', 'top', 'width', 'height'])
                                logger.debug(f"Field '{field_name}': bbox_keys={bbox_keys}, has_coords={has_coords}")
                            else:
                                logger.debug(f"Field '{field_name}': NO bbox in citation (type={type(bbox)})")

                            parsed_citations[field_name] = {
                                "confidence": float(confidence),
                                "bbox": bbox if isinstance(bbox, dict) else {},
                                "page": bbox.get("page", 1) if isinstance(bbox, dict) else 1
                            }

        return parsed_citations

    def _parse_extraction_with_complex_types(
        self,
        raw_extractions: Any,
        schema: Dict[str, Any],
        citations_data: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Parse Reducto extraction response handling complex types (arrays, tables).

        Args:
            raw_extractions: Raw extraction response from Reducto
            schema: Our schema with type information
            citations_data: Optional citation metadata with confidence scores

        Returns:
            Dict with normalized structure including complex types
        """
        if citations_data is None:
            citations_data = {}

        # Build field type map
        field_types = {}
        for field in schema.get("fields", []):
            field_types[field["name"]] = field.get("type", "text")

        parsed = {}

        # Handle dict format (most common)
        if isinstance(raw_extractions, dict):
            for field_name, field_data in raw_extractions.items():
                field_type = field_types.get(field_name, "text")

                # Extract value and metadata - support both v3 format and legacy format
                if isinstance(field_data, dict) and "value" in field_data:
                    # V3 format: {"value": "...", "citations": [...]}
                    value = field_data["value"]

                    # Extract bbox from embedded citations (v3 format)
                    citations_list = field_data.get("citations", [])
                    if citations_list and isinstance(citations_list, list) and len(citations_list) > 0:
                        first_citation = citations_list[0]

                        # Parse bbox from citation
                        bbox = first_citation.get("bbox", {})
                        page = bbox.get("page", 1) if isinstance(bbox, dict) else 1

                        # Parse confidence from citation (convert "high"/"medium"/"low" to float)
                        conf_str = first_citation.get("confidence", "high")
                        confidence = {"high": 0.9, "medium": 0.7, "low": 0.5}.get(conf_str, 0.85)

                        logger.debug(f"Field '{field_name}' v3 citation: conf={conf_str}→{confidence}, page={page}, bbox_keys={list(bbox.keys()) if bbox else 'none'}")
                    else:
                        # No citations in v3 format
                        confidence = field_data.get("confidence", 0.85)
                        bbox = field_data.get("bbox")
                        page = field_data.get("page", 1)
                else:
                    # Legacy format: direct value
                    value = field_data
                    confidence = 0.85
                    bbox = None
                    page = None

                # Override with citations data if available (legacy format from top-level citations array)
                if field_name in citations_data:
                    citation = citations_data[field_name]
                    confidence = citation.get("confidence", confidence)
                    bbox = citation.get("bbox", bbox)
                    page = citation.get("page", page)

                # Handle complex types
                if field_type in ["array", "array_of_objects", "table"]:
                    # Value should already be a list
                    if not isinstance(value, list):
                        value = []

                    # Calculate per-item/row confidence if available
                    if isinstance(value, list) and value:
                        item_confidences = []
                        for item in value:
                            if isinstance(item, dict) and "confidence" in item:
                                item_confidences.append(item["confidence"])
                        avg_confidence = sum(item_confidences) / len(item_confidences) if item_confidences else confidence
                    else:
                        avg_confidence = confidence

                    parsed[field_name] = {
                        "value": value,  # Keep as list/array
                        "field_type": field_type,
                        "confidence": float(avg_confidence),
                        "source_page": int(page) if page else None,
                        "source_bbox": bbox
                    }
                else:
                    # Simple type
                    parsed[field_name] = {
                        "value": str(value) if value is not None else "",
                        "field_type": field_type,
                        "confidence": float(confidence),
                        "source_page": int(page) if page else None,
                        "source_bbox": bbox
                    }

        # Handle list format
        elif isinstance(raw_extractions, list):
            # Check if list contains a single dict with field names as keys (new Reducto format)
            if (len(raw_extractions) == 1 and
                isinstance(raw_extractions[0], dict) and
                not any(k in raw_extractions[0] for k in ["field", "name", "value"])):
                # New format: [{"product_name": "Pinecone", "cloud_platform": "AWS", ...}]
                # Recursively call this function with the dict
                return self._parse_extraction_with_complex_types(raw_extractions[0], schema, citations_data)

            # Old format: [{"field": "product_name", "value": "...", ...}, ...]
            for extraction in raw_extractions:
                if not isinstance(extraction, dict):
                    continue

                field_name = extraction.get("field", extraction.get("name"))
                if not field_name:
                    continue

                field_type = field_types.get(field_name, "text")
                value = extraction.get("value", "")
                confidence = extraction.get("confidence", 0.85)
                bbox = extraction.get("bbox")
                page = extraction.get("page", 1)

                parsed[field_name] = {
                    "value": value if field_type in ["array", "array_of_objects", "table"] else str(value),
                    "field_type": field_type,
                    "confidence": float(confidence),
                    "source_page": int(page) if page else None,
                    "source_bbox": bbox
                }

        return parsed

