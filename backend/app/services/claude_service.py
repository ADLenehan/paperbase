import anthropic
from typing import Dict, Any, List, Optional
from datetime import datetime
import calendar
from app.core.config import settings
from app.core.exceptions import ClaudeError, SchemaError
import json
import logging

logger = logging.getLogger(__name__)


class ClaudeService:
    """
    Service for interacting with Anthropic Claude API for schema generation.

    Claude is used ONLY for:
    1. Initial schema generation from sample documents (onboarding)
    2. Improving extraction rules based on verification feedback (weekly)
    3. Suggesting new fields from natural language descriptions

    This minimizes per-document costs as Reducto handles all actual extraction.
    """

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.model = "claude-sonnet-4-20250514"  # Claude Sonnet 4 (latest)
        logger.debug(f"ClaudeService initialized with model: {self.model}")
        logger.debug(f"Client type: {type(self.client)}, has messages: {hasattr(self.client, 'messages')}")

    async def analyze_sample_documents(
        self,
        parsed_documents: List[Dict[str, Any]],
        user_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze sample documents and generate extraction schema with complexity assessment

        Args:
            parsed_documents: List of Reducto parsed documents

        Returns:
            {
                "name": "Service Agreements",
                "fields": [
                    {
                        "name": "effective_date",
                        "type": "date|text|number|boolean|array|table|array_of_objects",
                        "required": true,
                        "extraction_hints": ["Effective Date:", "Dated:"],
                        "confidence_threshold": 0.75,
                        "description": "Contract effective date",
                        # For arrays:
                        "item_type": "text|number|date",  # optional
                        # For tables:
                        "table_schema": {  # optional
                            "row_identifier": "pom_code",
                            "columns": ["size_2", "size_3"],
                            "dynamic_columns": true,
                            "value_type": "number"
                        },
                        # For array_of_objects:
                        "object_schema": {  # optional
                            "description": {"type": "text", "required": true},
                            "quantity": {"type": "number", "required": true}
                        }
                    },
                    ...
                ],
                "complexity_assessment": {  # NEW
                    "score": 45,
                    "confidence": 0.85,
                    "warnings": ["List of warnings"],
                    "recommendation": "auto|assisted|manual"
                }
            }
        """
        if not parsed_documents:
            raise SchemaError("No documents provided for analysis")

        # Build prompt with document samples and optional user context
        prompt = self._build_schema_generation_prompt(parsed_documents, user_context)

        logger.info(f"Requesting schema generation from Claude for {len(parsed_documents)} documents")

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            # Parse Claude's response
            response_text = message.content[0].text

            # Remove markdown code blocks if present
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]

            schema = json.loads(response_text.strip())

            # Validate schema structure
            if "name" not in schema or "fields" not in schema:
                raise SchemaError("Invalid schema format: missing 'name' or 'fields'")

            # Extract complexity assessment (optional for backward compatibility)
            complexity = schema.get("complexity_assessment", {
                "score": 0,
                "confidence": 0.0,
                "warnings": [],
                "recommendation": "auto"
            })

            num_fields = len(schema.get("fields", []))
            logger.info(
                f"Schema generated successfully: '{schema.get('name')}' "
                f"with {num_fields} fields, "
                f"complexity: {complexity.get('score')} ({complexity.get('recommendation')})"
            )

            return schema

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Claude response as JSON: {e}")
            logger.debug(f"Response text: {response_text[:500]}")
            raise ClaudeError("Claude did not return valid JSON schema", e)

        except anthropic.APIError as e:
            logger.error(f"Anthropic API error: {str(e)}")
            raise ClaudeError(f"API error during schema generation: {str(e)}", e)

        except Exception as e:
            logger.error(f"Error generating schema with Claude: {e}", exc_info=True)
            raise ClaudeError(f"Unexpected error during schema generation: {str(e)}", e)

    async def quick_analyze_document(
        self,
        parsed_document: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Quick document analysis to suggest context categories for schema generation.
        Analyzes the actual document structure and suggests what data can be extracted.

        Args:
            parsed_document: Single Reducto parsed document

        Returns:
            {
                "suggestions": [
                    "Table with measurements (columns: Size, Chest, Waist, Hip)",
                    "Repeated color/SKU information",
                    "Fabric composition details"
                ],
                "document_structure": {
                    "has_tables": true,
                    "table_count": 2,
                    "has_repeated_sections": true,
                    "section_count": 5
                }
            }
        """

        # Extract document sample
        chunks = parsed_document.get("result", {}).get("chunks", [])
        # Reducto v2 has nested structure: chunk['blocks'][i]['content']
        text_parts = []
        for chunk in chunks[:15]:
            # Try new format (blocks array)
            if 'blocks' in chunk and isinstance(chunk['blocks'], list):
                for block in chunk['blocks']:
                    if 'content' in block and block['content']:
                        text_parts.append(block['content'])
            # Fallback to old format (direct content field)
            elif chunk.get("content") or chunk.get("text"):
                text_parts.append(chunk.get("content", chunk.get("text", "")))

        text = "\n".join(text_parts)
        text_sample = text[:3000]  # First 3000 chars

        prompt = f"""Analyze this document and suggest what data can be extracted from it.

Document Sample:
{text_sample}

Your task:
1. Identify what types of information are present in this document
2. Look for tables, lists, repeated structures, key-value pairs
3. Suggest 3-5 specific data extraction opportunities

Return ONLY a JSON object with this structure:
{{
    "suggestions": [
        "Brief description of extractable data (e.g., 'Table with product measurements across multiple sizes')",
        "Another data opportunity",
        "..."
    ],
    "document_structure": {{
        "has_tables": true|false,
        "table_count": 0,
        "has_repeated_sections": true|false,
        "section_count": 0,
        "has_key_value_pairs": true|false
    }}
}}

Guidelines for suggestions:
- Be specific about table structures (mention columns if visible)
- Note repeated patterns (e.g., "Multiple product entries with SKU, color, size")
- Identify complex structures (e.g., "Nested bill of materials with quantities")
- Mention any domain-specific data (e.g., "Garment grading measurements", "Financial line items")
- Keep suggestions actionable and clear

Return ONLY the JSON, no markdown formatting."""

        logger.info("Requesting quick document analysis from Claude")

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=1024,  # Smaller response for quick analysis
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            # Parse Claude's response
            response_text = message.content[0].text

            # Remove markdown code blocks if present
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
                response_text = response_text.rsplit("```", 1)[0]

            analysis = json.loads(response_text.strip())

            logger.info(f"Quick analysis complete: {len(analysis.get('suggestions', []))} suggestions")

            return analysis

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse quick analysis response as JSON: {e}")
            logger.debug(f"Response text: {response_text[:500]}")
            raise ClaudeError("Claude did not return valid JSON for quick analysis", e)

        except anthropic.APIError as e:
            logger.error(f"Anthropic API error during quick analysis: {str(e)}")
            raise ClaudeError(f"API error during quick analysis: {str(e)}", e)

        except Exception as e:
            logger.error(f"Error during quick analysis: {e}", exc_info=True)
            raise ClaudeError(f"Unexpected error during quick analysis: {str(e)}", e)

    def _build_schema_generation_prompt(
        self,
        parsed_documents: List[Dict[str, Any]],
        user_context: Optional[str] = None
    ) -> str:
        """Build prompt for schema generation with optional user context"""

        # Extract text samples from documents
        document_samples = []
        for i, doc in enumerate(parsed_documents[:5]):  # Max 5 samples
            chunks = doc.get("result", {}).get("chunks", [])
            # Reducto uses 'content' field for text, fallback to 'text'
            text = "\n".join([chunk.get("content", chunk.get("text", "")) for chunk in chunks[:10]])  # First 10 chunks
            document_samples.append(f"## Document {i+1}\n{text[:2000]}")  # First 2000 chars

        samples_text = "\n\n".join(document_samples)

        # Add user context section if provided
        context_section = ""
        if user_context:
            context_section = f"""
User Context (what the user wants to extract):
{user_context}

Use this context to guide your field extraction. Pay special attention to the data structures and information the user mentioned.

"""

        prompt = f"""Analyze these sample documents and generate an extraction schema in JSON format.

Documents:
{samples_text}

{context_section}Your task:
1. Identify the common fields across all documents
2. Determine the data type for each field (text, date, number, boolean, array, table, array_of_objects)
3. Create extraction hints (keywords/phrases that appear near each field)
4. Set appropriate confidence thresholds (0.0-1.0)
5. Mark fields as required or optional
6. Assess the overall complexity of this schema

IMPORTANT - Reducto API Requirements (MANDATORY):
- **Every field MUST have a description** (minimum 10 characters)
- Descriptions act as prompts to guide extraction - be specific about what to extract
- Field names MUST be descriptive and use snake_case (e.g., "invoice_date" not "field1")
- Field names should match document terminology where possible (e.g., if doc says "PO Number", use "po_number")
- extraction_hints should include ACTUAL text from documents (labels, headers, keywords)
- Include multiple hint variations (e.g., ["Total:", "Total Amount:", "Grand Total:"])
- **NO CALCULATIONS**: Extract raw values only, never prompt for derived values (e.g., don't say "multiply X by Y")
- Use boolean type for yes/no fields (not text with "yes"/"no" values)
- Consider using enum values for fields with limited options (status, category, type)

Return ONLY a JSON object with this exact structure:
{{
    "name": "Document Type Name",
    "fields": [
        {{
            "name": "field_name",
            "type": "text|date|number|boolean|array|table|array_of_objects",
            "required": true|false,
            "extraction_hints": ["keyword1", "keyword2"],
            "confidence_threshold": 0.75,
            "description": "Brief description"
        }}
    ],
    "complexity_assessment": {{
        "score": 45,
        "confidence": 0.85,
        "warnings": ["List any concerns about auto-extraction reliability"],
        "recommendation": "auto|assisted|manual"
    }}
}}

Field Type Guidelines:
- **text**: Simple text values (names, addresses, descriptions)
- **date**: Date values in any format
- **number**: Numeric values (prices, quantities, percentages)
- **boolean**: Yes/no, true/false values
- **array**: List of simple values (e.g., ["Red", "Blue", "Green"])
  - Add "item_type": "text|number|date" to specify array item type
  - Example: {{"name": "colors", "type": "array", "item_type": "text"}}
- **table**: Structured data with rows and columns
  - Add "table_schema" with row_identifier and columns
  - Example: {{"name": "measurements", "type": "table", "table_schema": {{"row_identifier": "pom_code", "columns": ["size_2", "size_3"], "value_type": "number"}}}}
  - Use "dynamic_columns": true for variable columns
- **array_of_objects**: List of structured items (e.g., invoice line items)
  - Add "object_schema" defining the object structure
  - Example: {{"name": "line_items", "type": "array_of_objects", "object_schema": {{"description": {{"type": "text"}}, "quantity": {{"type": "number"}}}}}}

Complexity Assessment:
Calculate a complexity score (0-100+) based on:
- Field count × 3 (more fields = more complex)
- Nesting depth × 15 (tables, arrays of objects)
- Number of arrays × 10
- Table complexity × 20 (rows × columns, dynamic columns)
- Domain specificity × 10 (specialized terminology)
- Data variability × 5 (inconsistent formats)

Scoring Guidelines:
- 0-50: **auto** - Simple documents, high confidence (0.8-0.95)
  - Examples: Basic invoices (5-8 text/number fields), simple forms, receipts
- 51-80: **assisted** - Medium complexity, moderate confidence (0.6-0.75)
  - Examples: Contracts with tables, invoices with line items, multi-page forms
- 81+: **manual** - High complexity, low confidence (0.3-0.5)
  - Examples: Financial statements, technical specs with charts, garment grading tables
  - Warnings: "Contains complex multi-cell tables", "Multiple nested structures", "Graphs/charts detected"

Return ONLY the JSON, no markdown formatting or explanation."""

        return prompt

    async def generate_reducto_config(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert schema to Reducto extraction configuration

        Args:
            schema: Generated schema from analyze_sample_documents

        Returns:
            Reducto-compatible extraction config
        """
        reducto_config = {
            "schema_name": schema["name"],
            "fields": []
        }

        for field in schema["fields"]:
            reducto_field = {
                "name": field["name"],
                "type": field["type"],
                "hints": field["extraction_hints"],
                "required": field.get("required", False)
            }
            reducto_config["fields"].append(reducto_field)

        logger.info(f"Generated Reducto config for schema: {schema['name']}")
        return reducto_config

    async def improve_extraction_rules(
        self,
        field_name: str,
        failed_extractions: List[Dict[str, Any]],
        successful_extractions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Improve extraction rules based on verification feedback

        Args:
            field_name: Name of field to improve
            failed_extractions: Examples where extraction failed
            successful_extractions: Examples where extraction succeeded

        Returns:
            Improved field configuration with new hints
        """
        prompt = f"""Improve extraction rules for the field "{field_name}".

Failed Extractions:
{json.dumps(failed_extractions[:5], indent=2)}

Successful Extractions:
{json.dumps(successful_extractions[:5], indent=2)}

Based on these examples, suggest improved extraction hints and patterns.

Return JSON:
{{
    "extraction_hints": ["hint1", "hint2"],
    "patterns": ["regex1", "regex2"],
    "recommendations": "Brief explanation of improvements"
}}"""

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = message.content[0].text
            improvements = json.loads(response_text)

            logger.info(f"Generated improvements for field: {field_name}")
            return improvements

        except Exception as e:
            logger.error(f"Error improving extraction rules: {e}")
            raise

    async def suggest_field_from_description(self, description: str) -> Dict[str, Any]:
        """
        Generate field configuration from natural language description

        Args:
            description: Natural language description (e.g., "Add a field for invoice total")

        Returns:
            Field configuration
        """
        prompt = f"""Generate a field configuration for this request:
"{description}"

Return ONLY JSON:
{{
    "name": "field_name",
    "type": "date|text|number|boolean",
    "required": false,
    "extraction_hints": ["hint1", "hint2"],
    "confidence_threshold": 0.75,
    "description": "Brief description"
}}"""

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = message.content[0].text
            field_config = json.loads(response_text)

            logger.info(f"Generated field suggestion: {field_config.get('name')}")
            return field_config

        except Exception as e:
            logger.error(f"Error generating field suggestion: {e}")
            raise

    async def modify_schema_with_prompt(
        self,
        prompt: str,
        current_fields: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Modify schema fields using natural language prompt

        Args:
            prompt: User's natural language instruction (e.g., "Add a field for customer email")
            current_fields: Current schema fields

        Returns:
            Modified list of fields
        """
        system_prompt = """You are an expert at modifying document extraction schemas based on natural language instructions.

You will receive:
1. A user's instruction for modifying the schema
2. The current list of fields in the schema

Your task:
- Follow the user's instruction exactly
- Maintain the structure of existing fields
- When adding fields, use proper snake_case naming
- When modifying types, use: text, number, date, boolean, array, object
- Keep confidence_threshold between 0.6-0.9
- Ensure extraction_hints are relevant keywords

Return ONLY a JSON array of the modified fields, with no markdown formatting or explanation."""

        user_prompt = f"""Current schema fields:
{json.dumps(current_fields, indent=2)}

User instruction:
{prompt}

Return the complete modified fields array in JSON format."""

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )

            response_text = message.content[0].text.strip()

            # Remove markdown code blocks if present
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
                response_text = response_text.strip()

            modified_fields = json.loads(response_text)

            if not isinstance(modified_fields, list):
                raise ValueError("Response must be a list of fields")

            logger.info(f"Modified schema with prompt: '{prompt}' -> {len(modified_fields)} fields")
            return modified_fields

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Claude response as JSON: {e}")
            logger.debug(f"Response text: {response_text[:500]}")
            raise ClaudeError("Claude did not return valid JSON array", e)

        except anthropic.APIError as e:
            logger.error(f"Anthropic API error: {str(e)}")
            raise ClaudeError(f"API error during schema modification: {str(e)}", e)

        except Exception as e:
            logger.error(f"Error modifying schema with Claude: {e}", exc_info=True)
            raise ClaudeError(f"Unexpected error during schema modification: {str(e)}", e)

    async def match_document_to_template(
        self,
        parsed_document: Dict[str, Any],
        available_templates: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Analyze a document and find the best matching template

        Args:
            parsed_document: Reducto parsed document
            available_templates: List of available templates with their schemas

        Returns:
            {
                "template_id": int or None,
                "confidence": float (0.0-1.0),
                "reasoning": str,
                "needs_new_template": bool
            }
        """
        if not available_templates:
            return {
                "template_id": None,
                "confidence": 0.0,
                "reasoning": "No templates available",
                "needs_new_template": True
            }

        # Extract document text sample
        # NOTE: parsed_document IS the result dict (from document.reducto_parse_result)
        chunks = parsed_document.get("chunks", [])
        # Reducto v2 has nested structure: chunk['blocks'][i]['content']
        doc_text_parts = []
        for chunk in chunks[:10]:
            # Try new format (blocks array)
            if 'blocks' in chunk and isinstance(chunk['blocks'], list):
                for block in chunk['blocks']:
                    if 'content' in block and block['content']:
                        doc_text_parts.append(block['content'])
            # Fallback to old format (direct content field)
            elif chunk.get("content") or chunk.get("text"):
                doc_text_parts.append(chunk.get("content", chunk.get("text", "")))

        doc_text = "\n".join(doc_text_parts)[:2000]

        # DEBUG: Log what text we extracted
        logger.debug(f"Extracted text for template matching - length: {len(doc_text)}, first 200 chars: {doc_text[:200]}")

        # Build template descriptions
        template_info = []
        for template in available_templates:
            fields = [f["name"] for f in template.get("fields", [])]
            template_info.append({
                "id": template["id"],
                "name": template["name"],
                "category": template.get("category", "general"),
                "fields": fields
            })

        prompt = f"""Analyze this document and determine which template (if any) best matches it.

Document Sample:
{doc_text}

Available Templates:
{json.dumps(template_info, indent=2)}

Your task:
1. Analyze the document structure and content
2. Determine if it matches any available template
3. Provide confidence score (0.0-1.0)
4. If confidence < 0.7, recommend creating a new template

Return ONLY JSON:
{{
    "template_id": <id or null>,
    "confidence": <0.0-1.0>,
    "reasoning": "Brief explanation",
    "needs_new_template": <true|false>
}}"""

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = message.content[0].text.strip()
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
                response_text = response_text.strip()

            result = json.loads(response_text)

            logger.info(
                f"Template matching: template_id={result.get('template_id')}, "
                f"confidence={result.get('confidence')}"
            )
            return result

        except Exception as e:
            logger.error(f"Error matching document to template: {e}")
            logger.error(f"Client object type: {type(self.client)}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            raise ClaudeError(f"Template matching failed: {str(e)}", e)

    async def analyze_documents_for_grouping(
        self,
        parsed_documents: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Analyze multiple documents and group them by similarity

        Args:
            parsed_documents: List of Reducto parsed documents

        Returns:
            List of groups:
            [
                {
                    "document_indices": [0, 2, 5],
                    "suggested_name": "Invoices",
                    "confidence": 0.9,
                    "common_fields": ["invoice_number", "total", "date"]
                },
                ...
            ]
        """
        if not parsed_documents:
            return []

        # Extract samples from each document
        doc_samples = []
        for i, doc in enumerate(parsed_documents[:10]):  # Max 10 docs for grouping
            logger.debug(f"Document {i} type: {type(doc)}, keys: {list(doc.keys()) if isinstance(doc, dict) else 'not a dict'}")

            # Handle both dict and object access
            if isinstance(doc, dict):
                result = doc.get("result", {})
                chunks = result.get("chunks", []) if isinstance(result, dict) else []
            else:
                # Handle Pydantic objects
                result = getattr(doc, 'result', {})
                chunks = getattr(result, 'chunks', [])

            # Reducto uses 'content' field for text, fallback to 'text'
            text = "\n".join([
                chunk.get("content", chunk.get("text", "")) if isinstance(chunk, dict)
                else getattr(chunk, 'content', getattr(chunk, 'text', ""))
                for chunk in chunks[:5]
            ])[:1000]
            doc_samples.append(f"## Document {i}\n{text}")

        samples_text = "\n\n".join(doc_samples)
        logger.info(f"Samples text: '{samples_text}'")

        # If no text extracted, return single group with all documents
        if not samples_text.strip() or samples_text.strip() == "\n\n".join([f"## Document {i}\n" for i in range(len(doc_samples))]).strip():
            logger.warning("No text extracted from documents, returning single group")
            return [{
                "document_indices": list(range(len(parsed_documents))),
                "suggested_name": "Generic Documents",
                "confidence": 0.5,
                "common_fields": []
            }]

        prompt = f"""Analyze these documents and group them by similarity.

Documents:
{samples_text}

Your task:
1. Identify which documents are similar (same type/structure)
2. Group similar documents together
3. Suggest a name for each group
4. List common fields you'd expect to extract from each group

Return ONLY JSON array:
[
    {{
        "document_indices": [0, 2, 5],
        "suggested_name": "Document Type Name",
        "confidence": 0.9,
        "common_fields": ["field1", "field2"]
    }}
]"""

        try:
            logger.info(f"Sending prompt to Claude (first 500 chars): {prompt[:500]}")
            message = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = message.content[0].text.strip()
            logger.debug(f"Claude response (raw): {response_text[:500]}")

            # Handle markdown code blocks
            if "```" in response_text:
                # Extract JSON from between backticks
                parts = response_text.split("```")
                for part in parts:
                    part = part.strip()
                    if part.startswith("json"):
                        part = part[4:].strip()
                    # Try to parse this part as JSON
                    if part and (part.startswith("[") or part.startswith("{")):
                        response_text = part
                        break

            # Find the JSON array in the response
            start_idx = response_text.find("[")
            end_idx = response_text.rfind("]")

            if start_idx != -1 and end_idx != -1:
                response_text = response_text[start_idx:end_idx+1]

            logger.debug(f"Claude response (cleaned): {response_text[:500]}")

            if not response_text:
                raise ValueError("Empty response from Claude")

            groups = json.loads(response_text)

            logger.info(f"Grouped {len(parsed_documents)} documents into {len(groups)} groups")
            return groups

        except Exception as e:
            logger.error(f"Error grouping documents: {e}")
            raise ClaudeError(f"Document grouping failed: {str(e)}", e)

    async def natural_language_search(
        self,
        query: str,
        available_fields: List[str],
        conversation_history: List[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Convert natural language query to Elasticsearch query

        Args:
            query: Natural language search query
            available_fields: List of field names in the schema
            conversation_history: Previous queries for context

        Returns:
            {
                "elasticsearch_query": {...},
                "explanation": "What we're searching for",
                "field_mappings": {"total": "invoice_total", ...}
            }
        """
        history_context = ""
        if conversation_history:
            history_context = "\n\nPrevious conversation:\n" + "\n".join([
                f"User: {h['query']}\nAnswer: {h['answer']}"
                for h in conversation_history[-3:]  # Last 3 exchanges
            ])

        prompt = f"""Convert this natural language query into an Elasticsearch query.

Available fields: {', '.join(available_fields)}

User query: "{query}"{history_context}

Your task:
1. Identify which fields the user is asking about
2. Extract any filters, date ranges, or conditions
3. Build an Elasticsearch query
4. Explain what you're searching for

Return ONLY JSON:
{{
    "elasticsearch_query": {{
        "query": {{
            "bool": {{
                "must": [...],
                "filter": [...]
            }}
        }}
    }},
    "explanation": "Searching for...",
    "field_mappings": {{"user_term": "field_name"}}
}}

Examples:
- "invoices over $1000" → filter invoice_total > 1000
- "contracts from last month" → date range on effective_date
- "show me all purchase orders" → match document type"""

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = message.content[0].text.strip()
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
                response_text = response_text.strip()

            result = json.loads(response_text)

            logger.info(f"NL search: '{query}' → {result.get('explanation')}")
            return result

        except Exception as e:
            logger.error(f"Error in NL search: {e}")
            raise ClaudeError(f"Natural language search failed: {str(e)}", e)

    async def answer_question_about_results(
        self,
        query: str,
        search_results: List[Dict[str, Any]],
        total_count: int,
        include_confidence_metadata: bool = True
    ) -> Dict[str, Any]:
        """
        Generate natural language answer about search results with optional confidence metadata.

        Args:
            query: User's original query
            search_results: List of matching documents
            total_count: Total number of matches
            include_confidence_metadata: If True, include confidence scores and structured output

        Returns:
            If include_confidence_metadata=True:
                {
                    "answer": "Natural language answer",
                    "sources_used": [doc_id1, doc_id2, ...],
                    "low_confidence_warnings": [{doc_id, field, confidence}, ...],
                    "confidence_level": "high|medium|low"
                }
            If include_confidence_metadata=False:
                {
                    "answer": "Natural language answer"
                }
        """
        # Build enhanced results with confidence metadata
        results_summary = []
        for doc in search_results[:10]:  # Increased from 5 to 10
            doc_data = doc.get("data", {}) if "data" in doc else doc

            if include_confidence_metadata:
                # Extract confidence scores if available
                confidence_scores = doc_data.get("confidence_scores", {})

                # Calculate average confidence
                avg_conf = 0.0
                if confidence_scores:
                    avg_conf = sum(confidence_scores.values()) / len(confidence_scores)

                results_summary.append({
                    "document_id": doc.get("id"),
                    "filename": doc_data.get("filename", "Unknown"),
                    "fields": {k: v for k, v in doc_data.items()
                              if k not in ["filename", "full_text", "confidence_scores", "document_id"]},
                    "confidence_scores": confidence_scores,
                    "avg_confidence": round(avg_conf, 2)
                })
            else:
                # Legacy format (backward compatible)
                results_summary.append({
                    "filename": doc_data.get("filename"),
                    "fields": {k: v for k, v in doc_data.items() if k != "filename"}
                })

        if include_confidence_metadata:
            # Enhanced prompt with confidence awareness
            prompt = f"""Answer this question based on the search results. Pay attention to data quality.

User question: "{query}"

Found {total_count} matching documents.

Documents (with quality metadata):
{json.dumps(results_summary, indent=2)}

Instructions:
1. Provide a clear, concise answer (2-4 sentences)
2. Note which document IDs you used for factual claims
3. If using data with low confidence (<0.7), mention uncertainty

Return ONLY valid JSON with this structure:
{{
    "answer": "Your natural language answer here",
    "sources_used": [document_ids_you_referenced],
    "low_confidence_warnings": [
        {{"document_id": 123, "field": "field_name", "confidence": 0.55}}
    ],
    "confidence_level": "high or medium or low"
}}

Set confidence_level based on:
- high: All data >= 0.8 confidence
- medium: Some data 0.6-0.8 confidence
- low: Any data < 0.6 confidence"""
        else:
            # Legacy prompt (backward compatible)
            prompt = f"""Answer this question based on the search results.

User question: "{query}"

Found {total_count} matching documents.

Sample results:
{json.dumps(results_summary, indent=2)}

Provide a natural language answer:
- Summarize what was found
- Highlight key patterns or insights
- If there are interesting findings, mention them

Keep it concise (2-3 sentences)."""

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=1024,  # Increased for structured output
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = message.content[0].text.strip()

            if include_confidence_metadata:
                # Parse JSON response
                # Remove markdown code blocks if present
                if response_text.startswith("```"):
                    response_text = response_text.split("```")[1]
                    if response_text.startswith("json"):
                        response_text = response_text[4:]
                    response_text = response_text.strip()

                try:
                    structured_response = json.loads(response_text)

                    # Validate structure
                    if "answer" not in structured_response:
                        # Fallback if JSON parsing failed
                        logger.warning("Claude didn't return structured JSON, using fallback")
                        return {
                            "answer": response_text,
                            "sources_used": [],
                            "low_confidence_warnings": [],
                            "confidence_level": "unknown"
                        }

                    logger.info(f"Generated structured answer for query: {query}")
                    return structured_response

                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse Claude JSON response: {e}")
                    # Fallback to plain answer
                    return {
                        "answer": response_text,
                        "sources_used": [],
                        "low_confidence_warnings": [],
                        "confidence_level": "unknown"
                    }
            else:
                # Legacy mode - return plain text wrapped in dict
                logger.info(f"Generated answer for query: {query}")
                return {"answer": response_text}

        except Exception as e:
            logger.error(f"Error generating answer: {e}")
            return {
                "answer": f"Found {total_count} matching documents.",
                "sources_used": [],
                "low_confidence_warnings": [],
                "confidence_level": "unknown"
            }

    async def parse_natural_language_query(
        self,
        query: str,
        available_fields: List[str],
        field_metadata: Optional[Dict[str, Any]] = None,
        conversation_history: List[Dict[str, str]] = None,
        template_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Parse natural language query with advanced date parsing, fuzzy matching,
        and intent detection. Now enhanced with field metadata for better understanding.

        Args:
            query: Natural language query
            available_fields: List of field names
            field_metadata: Rich field context from SchemaRegistry
            conversation_history: Previous conversation for context
            template_context: Optional template-specific field information
                {"name": "Template Name", "fields": [{name, type, description}, ...]}

        Returns:
            {
                "query_type": "search|aggregation|anomaly|comparison",
                "needs_clarification": bool,
                "clarifying_question": str (if needs_clarification),
                "elasticsearch_query": {...},
                "explanation": str,
                "aggregation": {"type": "sum|avg|count|group_by", "field": "...", "value_field": "..."},
                "filters": {...},
                "date_range": {"from": "...", "to": "..."}
            }
        """
        from datetime import datetime, timedelta
        import calendar

        # Calculate current date context for smart date parsing
        today = datetime.now()
        current_year = today.year
        current_month = today.month
        current_quarter = (current_month - 1) // 3 + 1

        # Calculate common date ranges
        date_context = {
            "today": today.strftime("%Y-%m-%d"),
            "yesterday": (today - timedelta(days=1)).strftime("%Y-%m-%d"),
            "current_year": current_year,
            "current_month": current_month,
            "current_quarter": current_quarter,
            "last_month": {
                "start": (today.replace(day=1) - timedelta(days=1)).replace(day=1).strftime("%Y-%m-%d"),
                "end": (today.replace(day=1) - timedelta(days=1)).strftime("%Y-%m-%d")
            },
            "last_quarter": self._calculate_last_quarter(today),
            "year_to_date": {
                "start": f"{current_year}-01-01",
                "end": today.strftime("%Y-%m-%d")
            },
            "last_30_days": {
                "start": (today - timedelta(days=30)).strftime("%Y-%m-%d"),
                "end": today.strftime("%Y-%m-%d")
            }
        }

        history_context = ""
        if conversation_history:
            history_context = "\n\nPrevious conversation:\n" + "\n".join([
                f"User: {h.get('query', '')}\nResponse: {h.get('answer', '')}"
                for h in conversation_history[-2:]
            ])

        # NEW: Build comprehensive semantic field mapping guide (ALWAYS-ON, not template-specific)
        semantic_guide = self._build_semantic_field_mapping_guide(
            available_fields=available_fields,
            field_metadata=field_metadata,
            template_context=template_context
        )

        # Build enriched field descriptions for additional reference
        field_descriptions = self._build_field_descriptions(available_fields, field_metadata)

        # Extract template routing hints if available (helps decide field vs full_text)
        template_routing = ""
        if template_context:
            template_name = template_context.get("name", "Unknown")

            # Check if template has search guidance metadata
            search_hints = template_context.get("search_hints", [])
            not_extracted = template_context.get("not_extracted", [])

            if search_hints or not_extracted:
                template_routing = f"""

📍 SEARCH ROUTING GUIDANCE for "{template_name}":
"""
                if search_hints:
                    template_routing += f"""
✅ EXTRACTED FIELDS cover: {', '.join(search_hints)}
   → Use multi_match with field boosting (field^10, full_text^1)
"""
                if not_extracted:
                    template_routing += f"""
❌ NOT IN FIELDS (requires full_text search): {', '.join(not_extracted)}
   → Use match on full_text or _all_text only
"""
                template_routing += f"""
⚠️  Template filter is automatic - DO NOT add template_name to your query filters
"""

        prompt = f"""You are a SEMANTIC QUERY TRANSLATOR for document search.

YOUR CRITICAL MISSION: Map user's natural language to PRECISE search fields.

{semantic_guide}
{template_routing}

Current date: {today.strftime("%Y-%m-%d")}
Date context: {json.dumps(date_context, indent=2)}

Additional field information:
{field_descriptions}

User query: "{query}"{history_context}

YOUR PROCESS:
1. **Semantic Field Mapping** (HIGHEST PRIORITY):
   - Extract key terms from user query
   - Match terms to field names using the mapping guide above
   - Generate multi_match query with field boosting

2. **Query Type Detection**:
   - search: Find specific documents
   - aggregation: Calculate totals/averages/counts
   - anomaly: Find unusual patterns (duplicates, outliers)
   - comparison: Compare time periods

3. **Filter Extraction**:
   - Date ranges (use date_context above for "last month", "Q4 2024", etc.)
   - Numeric ranges (amounts, counts)
   - Text filters (vendors, statuses)
   - Use fuzzy matching for text (e.g., "Acme" matches "Acme Corp", "ACME Inc")

4. **Clarification Detection**:
   - If query is ambiguous, set needs_clarification=true
   - Ask a specific question to clarify user intent

Return ONLY JSON (no markdown, no explanation outside JSON):
{{
    "query_type": "search|aggregation|anomaly|comparison",
    "needs_clarification": false,
    "clarifying_question": null,
    "elasticsearch_query": {{
        "query": {{
            "multi_match": {{
                "query": "search terms",
                "fields": ["specific_field^10", "related_field^5", "full_text^1"],
                "type": "best_fields"
            }}
        }}
    }},
    "explanation": "Human-readable explanation",
    "aggregation": {{"type": "sum|avg|count|group_by", "field": "field_name", "value_field": "optional"}},
    "filters": {{"field": "value"}},
    "date_range": {{"from": "YYYY-MM-DD", "to": "YYYY-MM-DD"}}
}}

QUERY CONSTRUCTION RULES:
- ✅ ALWAYS use multi_match with field boosting for search queries
- ✅ Map query terms to fields using the semantic guide above
- ✅ Use "range" queries for dates and numbers in filter clauses
- ✅ Use "term" queries for exact matches (status, IDs) in filter clauses
- ✅ Use fuzzy "match" queries for text (vendor names, descriptions)
- ❌ NEVER create {{"match": {{"full_text": "..."}}}} queries (too broad)
- ❌ NEVER add template_name filters (system handles this automatically)

CONCRETE EXAMPLES:

Example 1: Field-Specific Search
Query: "what cloud platform is used?"
Analysis: "cloud" + "platform" → matches field "cloud_platform"
Generated Query:
{{
  "multi_match": {{
    "query": "cloud platform",
    "fields": ["cloud_platform^10", "full_text^1"],
    "type": "best_fields"
  }}
}}

Example 2: Cross-Field Range Query
Query: "invoices over $5000 last quarter"
Analysis: "invoices" + "$5000" → amount field range + date filter
Generated Query:
{{
  "bool": {{
    "must": [
      {{"multi_match": {{"query": "invoices", "fields": ["full_text"]}}}}
    ],
    "filter": [
      {{"range": {{"invoice_total": {{"gte": 5000}}}}}},
      {{"range": {{"date": {{"gte": "{date_context['last_quarter']['start']}", "lte": "{date_context['last_quarter']['end']}"}}}}}}
    ]
  }}
}}

Example 3: Aggregation Query
Query: "total spending by vendor this year"
Generated Query:
{{
  "bool": {{
    "filter": [
      {{"range": {{"date": {{"gte": "{current_year}-01-01"}}}}}}
    ]
  }}
}}
Aggregation: {{"type": "sum", "field": "invoice_total", "group_by": "vendor_name"}}

Now parse the user query above and return ONLY the JSON response."""

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = message.content[0].text.strip()

            # Remove markdown code blocks
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
                response_text = response_text.strip()

            result = json.loads(response_text)

            logger.info(f"Parsed NL query: type={result.get('query_type')}, "
                       f"needs_clarification={result.get('needs_clarification')}")

            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Claude response: {e}")
            logger.debug(f"Response text: {response_text[:500]}")
            raise ClaudeError("Failed to parse query", e)

        except Exception as e:
            logger.error(f"Error parsing NL query: {e}")
            raise ClaudeError(f"Query parsing failed: {str(e)}", e)

    def _calculate_last_quarter(self, date: datetime) -> Dict[str, str]:
        """Calculate the date range for the previous complete quarter."""
        current_month = date.month
        current_quarter = (current_month - 1) // 3 + 1
        last_quarter = current_quarter - 1 if current_quarter > 1 else 4
        year = date.year if current_quarter > 1 else date.year - 1

        # Calculate start and end months for the quarter
        quarter_start_month = (last_quarter - 1) * 3 + 1
        quarter_end_month = last_quarter * 3

        start_date = datetime(year, quarter_start_month, 1)
        _, last_day = calendar.monthrange(year, quarter_end_month)
        end_date = datetime(year, quarter_end_month, last_day)

        return {
            "start": start_date.strftime("%Y-%m-%d"),
            "end": end_date.strftime("%Y-%m-%d"),
            "quarter": last_quarter,
            "year": year
        }

    def _build_semantic_field_mapping_guide(
        self,
        available_fields: List[str],
        field_metadata: Optional[Dict[str, Any]],
        template_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Build comprehensive semantic field mapping guide for Claude.
        This is the CORE of the field mapping solution - teaches Claude how to map
        query terms to actual field names.

        Args:
            available_fields: List of field names
            field_metadata: Rich field context from SchemaRegistry
            template_context: Optional template-specific context

        Returns:
            Formatted guide string with examples and rules
        """
        guide_parts = []

        # Header
        guide_parts.append("=" * 80)
        guide_parts.append("🎯 SEMANTIC FIELD MAPPING GUIDE (CRITICAL)")
        guide_parts.append("=" * 80)
        guide_parts.append("")

        # Build canonical field mappings table
        canonical_patterns = {
            "amount": ["total", "amount", "cost", "price", "value", "payment", "fee", "charge"],
            "date": ["date", "created", "when", "time"],
            "start_date": ["start", "effective", "begin", "commence", "from"],
            "end_date": ["end", "expir", "terminat", "until", "to"],
            "entity_name": ["vendor", "supplier", "customer", "client", "company", "organization"],
            "identifier": ["number", "id", "reference", "ref", "code"],
            "status": ["status", "state", "condition", "stage"],
        }

        # Group available fields by canonical category
        canonical_mapping = {}
        field_examples = {}

        for field_name in available_fields:
            field_lower = field_name.lower()
            matched = False

            # Try to match to canonical categories
            for canonical, patterns in canonical_patterns.items():
                if any(p in field_lower for p in patterns):
                    if canonical not in canonical_mapping:
                        canonical_mapping[canonical] = []
                        field_examples[canonical] = []

                    canonical_mapping[canonical].append(field_name)

                    # Extract example terms from field name for mapping
                    terms = field_name.replace("_", " ").lower().split()
                    field_examples[canonical].extend(terms)
                    matched = True
                    break

        # Section 1: Canonical Field Mappings
        if canonical_mapping:
            guide_parts.append("📋 CANONICAL FIELD MAPPINGS (Use these for cross-template queries):")
            guide_parts.append("")

            for canonical, fields in canonical_mapping.items():
                if len(fields) >= 1:
                    examples = list(set(field_examples.get(canonical, [])))[:5]
                    guide_parts.append(f"  {canonical}:")
                    guide_parts.append(f"    → Actual fields: {', '.join(fields)}")
                    guide_parts.append(f"    → Query terms: {', '.join(examples)}")
                    guide_parts.append("")

            guide_parts.append("")

        # Section 2: Field-Specific Mappings (if template provided)
        if template_context:
            template_name = template_context.get("name", "Unknown")
            template_fields = template_context.get("fields", [])

            guide_parts.append(f"🎯 TEMPLATE-SPECIFIC MAPPINGS (Template: '{template_name}'):")
            guide_parts.append("")

            for field in template_fields[:10]:  # Top 10 fields
                field_name = field.get("name", "")
                field_type = field.get("type", "text")
                field_desc = field.get("description", "")

                # Extract semantic terms from field name
                terms = field_name.replace("_", " ").lower().split()
                query_terms = ", ".join(terms)

                guide_parts.append(f"  Field: {field_name} ({field_type})")
                if field_desc:
                    guide_parts.append(f"    Description: {field_desc}")
                guide_parts.append(f"    Query terms that should map to this field: {query_terms}")
                guide_parts.append("")

        # Section 3: Concrete Examples
        guide_parts.append("=" * 80)
        guide_parts.append("📚 CONCRETE MAPPING EXAMPLES")
        guide_parts.append("=" * 80)
        guide_parts.append("")

        # Generate examples based on actual available fields
        example_counter = 1

        # Example 1: Field-specific search
        if canonical_mapping:
            for canonical, fields in list(canonical_mapping.items())[:1]:  # First canonical type
                field = fields[0]
                field_terms = field.replace("_", " ")

                guide_parts.append(f"Example {example_counter}: Field-Specific Search")
                guide_parts.append(f"  User Query: \"what is the {field_terms}?\"")
                guide_parts.append(f"  Analysis:")
                guide_parts.append(f"    - Key terms: {', '.join(field_terms.split())}")
                guide_parts.append(f"    - Matching field: '{field}' (contains matching terms)")
                guide_parts.append(f"    - Strategy: Search specific field with high boost")
                guide_parts.append(f"  ")
                guide_parts.append(f"  Generated Query:")
                guide_parts.append(f"  {{")
                guide_parts.append(f"    \"multi_match\": {{")
                guide_parts.append(f"      \"query\": \"{field_terms}\",")
                guide_parts.append(f"      \"fields\": [\"{field}^10\", \"full_text^1\"],")
                guide_parts.append(f"      \"type\": \"best_fields\"")
                guide_parts.append(f"    }}")
                guide_parts.append(f"  }}")
                guide_parts.append("")
                example_counter += 1

        # Example 2: Cross-template canonical search
        if len(canonical_mapping.get("amount", [])) > 1:
            amount_fields = canonical_mapping["amount"]
            guide_parts.append(f"Example {example_counter}: Cross-Template Canonical Search")
            guide_parts.append(f"  User Query: \"show me amounts over $1000\"")
            guide_parts.append(f"  Analysis:")
            guide_parts.append(f"    - Key term: 'amount' (canonical category)")
            guide_parts.append(f"    - Mapped to fields: {', '.join(amount_fields)}")
            guide_parts.append(f"    - Strategy: Search ALL amount fields across templates")
            guide_parts.append(f"  ")
            guide_parts.append(f"  Generated Query:")
            guide_parts.append(f"  {{")
            guide_parts.append(f"    \"bool\": {{")
            guide_parts.append(f"      \"should\": [")
            for field in amount_fields:
                guide_parts.append(f"        {{\"range\": {{\"{field}\": {{\"gte\": 1000}}}}}},")
            guide_parts.append(f"      ],")
            guide_parts.append(f"      \"minimum_should_match\": 1")
            guide_parts.append(f"    }}")
            guide_parts.append(f"  }}")
            guide_parts.append("")
            example_counter += 1

        # Section 4: Mandatory Rules
        guide_parts.append("=" * 80)
        guide_parts.append("⚠️  MANDATORY QUERY CONSTRUCTION RULES")
        guide_parts.append("=" * 80)
        guide_parts.append("")

        guide_parts.append("Rule 1: ALWAYS USE MULTI_MATCH WITH FIELD BOOSTING")
        guide_parts.append("  ✅ CORRECT:")
        guide_parts.append("  {\"multi_match\": {\"query\": \"...\", \"fields\": [\"specific_field^10\", \"full_text^1\"]}}")
        guide_parts.append("")
        guide_parts.append("  ❌ WRONG:")
        guide_parts.append("  {\"match\": {\"full_text\": \"...\"}}  // Too broad, searches 10,000+ words")
        guide_parts.append("")

        guide_parts.append("Rule 2: MAP QUERY TERMS TO FIELD NAMES")
        guide_parts.append("  Process:")
        guide_parts.append("    1. Extract key terms from user query")
        guide_parts.append("    2. Match terms to field names (exact or partial)")
        guide_parts.append("    3. Boost matched fields 10x, related fields 5x, full_text 1x")
        guide_parts.append("")

        guide_parts.append("Rule 3: NEVER CREATE FULL_TEXT-ONLY QUERIES")
        guide_parts.append("  If a specific field exists for the query intent, SEARCH THAT FIELD FIRST")
        guide_parts.append("  Use full_text only as fallback, not primary search target")
        guide_parts.append("")

        guide_parts.append("Rule 4: FOR CANONICAL QUERIES (no template filter)")
        guide_parts.append("  Search ALL fields matching the canonical category")
        guide_parts.append("  Use bool→should with minimum_should_match: 1")
        guide_parts.append("")

        guide_parts.append("=" * 80)
        guide_parts.append("")

        return "\n".join(guide_parts)

    def _build_field_descriptions(
        self,
        available_fields: List[str],
        field_metadata: Optional[Dict[str, Any]]
    ) -> str:
        """
        Build enriched field descriptions for the LLM prompt.

        Uses field metadata to provide context about aliases, types, canonical mappings,
        and usage patterns. This helps Claude generate more accurate queries.
        """
        if not field_metadata or not field_metadata.get("fields"):
            # Fallback to simple list
            return ", ".join(available_fields)

        descriptions = []
        fields_dict = field_metadata.get("fields", {})

        # Build canonical mapping info for context
        canonical_info = {}
        canonical_patterns = {
            "amount": ["total", "amount", "cost", "price", "value", "payment"],
            "date": ["date", "created", "when"],
            "start_date": ["start", "effective", "begin"],
            "end_date": ["end", "expir", "terminat"],
            "entity_name": ["vendor", "supplier", "customer", "client", "company"],
            "identifier": ["number", "id", "reference"],
            "status": ["status", "state"],
        }

        # Group fields by canonical category
        for field_name in available_fields:
            field_lower = field_name.lower()
            for canonical, patterns in canonical_patterns.items():
                if any(p in field_lower for p in patterns):
                    if canonical not in canonical_info:
                        canonical_info[canonical] = []
                    canonical_info[canonical].append(field_name)
                    break

        # Add canonical mapping header
        if canonical_info:
            descriptions.append("**Canonical Field Mappings** (use these for cross-template queries):")
            for canonical, fields in canonical_info.items():
                if len(fields) > 1:
                    descriptions.append(f"  - {canonical}: {', '.join(fields)}")
            descriptions.append("")  # Blank line

        descriptions.append("**Individual Fields:**")

        for field_name in available_fields:
            field_info = fields_dict.get(field_name, {})

            # Build description line
            parts = [f"- {field_name}"]

            # Add type
            field_type = field_info.get("type", "text")
            parts.append(f"({field_type})")

            # Add aliases if available
            aliases = field_info.get("aliases", [])
            if aliases:
                parts.append(f"aka: {', '.join(aliases[:3])}")  # Limit to 3 aliases

            # Add canonical mapping
            field_lower = field_name.lower()
            for canonical, patterns in canonical_patterns.items():
                if any(p in field_lower for p in patterns):
                    parts.append(f"[canonical: {canonical}]")
                    break

            # Add description if available
            description = field_info.get("description", "")
            if description:
                parts.append(f"- {description}")

            # Add extraction hints (shows what text appears near this field)
            hints = field_info.get("extraction_hints", [])
            if hints:
                hints_str = ", ".join([f'"{h}"' for h in hints[:3]])
                parts.append(f"[found near: {hints_str}]")

            descriptions.append(" ".join(parts))

        return "\n".join(descriptions)

    async def generate_query_summary(
        self,
        query: str,
        results: List[Dict[str, Any]],
        total_count: int,
        query_type: str,
        aggregations: Dict[str, Any] = None
    ) -> str:
        """
        Generate a conversational summary of query results with insights.
        """

        # Prepare results summary
        results_preview = []
        for r in results[:5]:
            data = r.get("data", {})
            results_preview.append({
                "filename": data.get("filename", "Unknown"),
                "key_fields": {
                    k: v for k, v in data.items()
                    if k in ["vendor", "total", "amount", "date", "status", "invoice_number"]
                }
            })

        agg_summary = ""
        if aggregations:
            agg_summary = f"\n\nAggregations:\n{json.dumps(aggregations, indent=2)}"

        prompt = f"""Generate a conversational summary of these query results.

User asked: "{query}"
Query type: {query_type}
Found: {total_count} documents

Sample results:
{json.dumps(results_preview, indent=2)}{agg_summary}

Your task:
1. Provide a clear, conversational summary (2-4 sentences)
2. Highlight key insights or patterns
3. Mention noteworthy findings (high/low values, trends, anomalies)
4. For aggregations, explain the numbers in context

Examples:
- "Found 23 invoices from Acme Corp totaling $47,200. The largest invoice was $8,500, and 3 are currently past due."
- "You've received 145 invoices this quarter, averaging $2,340 each. Your top vendor is Acme Corp with $31,000 in invoices."
- "Found 4 potential duplicate invoices. These have identical amounts and dates from the same vendors."

Keep it professional but conversational."""

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}]
            )

            summary = message.content[0].text.strip()
            logger.info(f"Generated summary for {total_count} results")
            return summary

        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            # Fallback summary
            if query_type == "aggregation" and aggregations:
                if aggregations.get("type") == "sum":
                    return f"Found {total_count} documents with a total of {aggregations.get('total', 0):.2f} for {aggregations.get('field')}."
                elif aggregations.get("type") == "avg":
                    return f"Found {total_count} documents with an average of {aggregations.get('average', 0):.2f} for {aggregations.get('field')}."
            return f"Found {total_count} matching documents."

    async def assess_document_complexity(
        self,
        parsed_documents: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Assess document complexity before attempting auto-generation.

        Returns:
            {
                "complexity_score": int (0-100+),
                "recommendation": "auto" | "assisted" | "manual",
                "confidence": float (0.0-1.0),
                "warnings": List[str],
                "detected_features": {
                    "field_count_estimate": int,
                    "has_tables": bool,
                    "has_arrays": bool,
                    "nesting_depth": int,
                    "domain": str
                }
            }
        """
        if not parsed_documents:
            return {
                "complexity_score": 0,
                "recommendation": "manual",
                "confidence": 0.0,
                "warnings": ["No documents provided"],
                "detected_features": {}
            }

        # Analyze first document to estimate complexity
        doc = parsed_documents[0]
        chunks = doc.get("result", {}).get("chunks", [])
        text_sample = "\n".join([c.get("content", c.get("text", "")) for c in chunks[:20]])

        # Extract features
        features = self._extract_complexity_features(text_sample)

        # Calculate complexity score
        score = (
            (features["field_count"] * 3) +
            (features["nesting_depth"] * 15) +
            (features["array_count"] * 10) +
            (features["table_complexity"] * 20) +
            (features["domain_specificity"] * 10) +
            (features["variability"] * 5)
        )

        # Determine recommendation
        if score <= 50:
            recommendation = "auto"
            confidence = 0.85
        elif score <= 80:
            recommendation = "assisted"
            confidence = 0.65
        else:
            recommendation = "manual"
            confidence = 0.35

        # Generate warnings
        warnings = []
        if features["field_count"] > 15:
            warnings.append(f"High field count ({features['field_count']}) may exceed auto-generation capabilities (recommended: 5-15)")
        if features["nesting_depth"] > 2:
            warnings.append("Deep nesting detected - manual schema recommended")
        if features["table_complexity"] > 1:
            warnings.append("Complex table structure detected - may require manual column definitions")
        if features["domain_specificity"] > 1:
            warnings.append(f"Specialized domain terminology detected ({features.get('detected_domain', 'unknown')})")

        logger.info(
            f"Complexity assessment: score={score}, recommendation={recommendation}, "
            f"fields={features['field_count']}, tables={features['has_tables']}"
        )

        return {
            "complexity_score": score,
            "recommendation": recommendation,
            "confidence": confidence,
            "warnings": warnings,
            "detected_features": features
        }

    def _extract_complexity_features(self, text: str) -> Dict[str, Any]:
        """
        Extract complexity indicators from document text.
        """
        import re

        # Count potential field labels (Pattern: "Label: Value")
        label_pattern = r'([A-Z][a-zA-Z\s]{2,30}):\s*[^\n]+'
        field_labels = re.findall(label_pattern, text)
        field_count = len(set(field_labels))

        # Detect tables (multiple rows with consistent column structure)
        has_table = bool(re.search(r'(\|.*\|.*\|)|(<table>)', text, re.IGNORECASE))
        table_rows = len(re.findall(r'\|.*\|.*\|', text))
        table_complexity = 0
        if has_table and table_rows > 10:
            table_complexity = 2  # Large table
        elif has_table:
            table_complexity = 1  # Small table

        # Detect arrays (repeating patterns)
        has_arrays = bool(re.search(r'(Item \d+|Line \d+|\d+\.|#\d+)', text))
        array_count = len(re.findall(r'(Item \d+|Line \d+)', text))
        array_count = min(array_count // 3, 5)  # Normalize

        # Estimate nesting (arrays with sub-fields)
        nesting_depth = 0
        if has_arrays:
            nesting_depth = 1
            # Check if array items have sub-structure
            if re.search(r'(Item \d+.*Description:.*Price:)', text, re.DOTALL):
                nesting_depth = 2

        # Detect domain specificity
        domain_keywords = {
            "medical": ["diagnosis", "prescription", "patient", "dosage", "lab result"],
            "legal": ["whereas", "party a", "party b", "covenant", "jurisdiction"],
            "financial": ["invoice", "payment", "total", "tax", "subtotal"],
            "scientific": ["hypothesis", "methodology", "coefficient", "specimen"],
            "engineering": ["specification", "tolerance", "dimension", "material"]
        }

        domain_specificity = 0
        detected_domain = "general"
        text_lower = text.lower()
        for domain, keywords in domain_keywords.items():
            if sum(1 for kw in keywords if kw in text_lower) >= 2:
                if domain in ["medical", "scientific", "engineering"]:
                    domain_specificity = 3  # Highly specialized
                    detected_domain = domain
                elif domain == "legal":
                    domain_specificity = 2  # Moderately specialized
                    detected_domain = domain
                else:
                    domain_specificity = 0  # General business
                    detected_domain = domain
                break

        return {
            "field_count": field_count,
            "has_tables": has_table,
            "table_complexity": table_complexity,
            "has_arrays": has_arrays,
            "array_count": array_count,
            "nesting_depth": nesting_depth,
            "domain_specificity": domain_specificity,
            "detected_domain": detected_domain,
            "variability": 0  # Can only assess with multiple docs
        }
