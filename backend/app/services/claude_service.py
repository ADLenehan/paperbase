import anthropic
from typing import Dict, Any, List, Optional
from datetime import datetime
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
        self.model = "claude-3-5-sonnet-20241022"
        logger.debug(f"ClaudeService initialized with model: {self.model}")
        logger.debug(f"Client type: {type(self.client)}, has messages: {hasattr(self.client, 'messages')}")

    async def analyze_sample_documents(
        self,
        parsed_documents: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Analyze sample documents and generate extraction schema

        Args:
            parsed_documents: List of Reducto parsed documents

        Returns:
            {
                "name": "Service Agreements",
                "fields": [
                    {
                        "name": "effective_date",
                        "type": "date",
                        "required": true,
                        "extraction_hints": ["Effective Date:", "Dated:"],
                        "confidence_threshold": 0.75,
                        "description": "Contract effective date"
                    },
                    ...
                ]
            }
        """
        if not parsed_documents:
            raise SchemaError("No documents provided for analysis")

        # Build prompt with document samples
        prompt = self._build_schema_generation_prompt(parsed_documents)

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

            num_fields = len(schema.get("fields", []))
            logger.info(
                f"Schema generated successfully: '{schema.get('name')}' "
                f"with {num_fields} fields"
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

    def _build_schema_generation_prompt(
        self,
        parsed_documents: List[Dict[str, Any]]
    ) -> str:
        """Build prompt for schema generation"""

        # Extract text samples from documents
        document_samples = []
        for i, doc in enumerate(parsed_documents[:5]):  # Max 5 samples
            chunks = doc.get("result", {}).get("chunks", [])
            # Reducto uses 'content' field for text, fallback to 'text'
            text = "\n".join([chunk.get("content", chunk.get("text", "")) for chunk in chunks[:10]])  # First 10 chunks
            document_samples.append(f"## Document {i+1}\n{text[:2000]}")  # First 2000 chars

        samples_text = "\n\n".join(document_samples)

        prompt = f"""Analyze these sample documents and generate an extraction schema in JSON format.

Documents:
{samples_text}

Your task:
1. Identify the common fields across all documents
2. Determine the data type for each field (text, date, number, boolean, etc.)
3. Create extraction hints (keywords/phrases that appear near each field)
4. Set appropriate confidence thresholds (0.0-1.0)
5. Mark fields as required or optional

Return ONLY a JSON object with this exact structure:
{{
    "name": "Document Type Name",
    "fields": [
        {{
            "name": "field_name",
            "type": "date|text|number|boolean",
            "required": true|false,
            "extraction_hints": ["keyword1", "keyword2"],
            "confidence_threshold": 0.75,
            "description": "Brief description"
        }}
    ]
}}

Important:
- Use snake_case for field names
- extraction_hints should be actual text snippets from the documents
- Set confidence_threshold between 0.6-0.9 based on field importance
- Include 5-15 fields (focus on the most important ones)
- Return ONLY the JSON, no markdown formatting or explanation"""

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
        chunks = parsed_document.get("result", {}).get("chunks", [])
        # Reducto uses 'content' field for text, fallback to 'text'
        doc_text = "\n".join([chunk.get("content", chunk.get("text", "")) for chunk in chunks[:10]])[:2000]

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
        total_count: int
    ) -> str:
        """
        Generate natural language answer about search results

        Args:
            query: User's original query
            search_results: List of matching documents
            total_count: Total number of matches

        Returns:
            Natural language answer
        """
        # Summarize results
        results_summary = []
        for doc in search_results[:5]:  # First 5 results
            results_summary.append({
                "filename": doc.get("filename"),
                "fields": {k: v for k, v in doc.items() if k != "filename"}
            })

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
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}]
            )

            answer = message.content[0].text.strip()
            logger.info(f"Generated answer for query: {query}")
            return answer

        except Exception as e:
            logger.error(f"Error generating answer: {e}")
            return f"Found {total_count} matching documents."

    async def parse_natural_language_query(
        self,
        query: str,
        available_fields: List[str],
        field_metadata: Optional[Dict[str, Any]] = None,
        conversation_history: List[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Parse natural language query with advanced date parsing, fuzzy matching,
        and intent detection. Now enhanced with field metadata for better understanding.

        Args:
            query: Natural language query
            available_fields: List of field names
            field_metadata: Rich field context from SchemaRegistry
            conversation_history: Previous conversation for context

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

        # NEW: Build enriched field descriptions using metadata
        field_descriptions = self._build_field_descriptions(available_fields, field_metadata)

        prompt = f"""You are an expert at parsing natural language queries for document search.
Current date: {today.strftime("%Y-%m-%d")}
Date context: {json.dumps(date_context, indent=2)}

Available fields with context:
{field_descriptions}

User query: "{query}"{history_context}

Your task:
1. Determine query type (search, aggregation, anomaly, comparison)
2. Parse date references (last month, Q4 2024, this year, etc.) using date_context
3. Extract filters (vendors, amounts, statuses, etc.)
4. Handle fuzzy matching (e.g., "Acme" should match "Acme Corp", "ACME Inc")
5. Detect if clarification is needed (ambiguous query)
6. Build appropriate Elasticsearch query

Query types:
- search: Find specific documents ("show me invoices from Acme")
- aggregation: Calculate totals/averages ("total spending by vendor", "average invoice amount")
- anomaly: Find unusual patterns ("duplicate invoices", "unusually high amounts")
- comparison: Compare time periods ("last month vs this month")

Return ONLY JSON:
{{
    "query_type": "search|aggregation|anomaly|comparison",
    "needs_clarification": false,
    "clarifying_question": null,
    "elasticsearch_query": {{
        "query": {{
            "bool": {{
                "must": [...],
                "filter": [...],
                "should": [...]
            }}
        }}
    }},
    "explanation": "Human-readable explanation of what we're searching for",
    "aggregation": {{"type": "sum|avg|count|group_by", "field": "field_name", "value_field": "optional"}},
    "filters": {{"field": "value"}},
    "date_range": {{"from": "YYYY-MM-DD", "to": "YYYY-MM-DD"}}
}}

Important:
- Use "match" queries for fuzzy text matching (e.g., vendor names)
- Use "range" queries for dates and numbers
- Use "term" queries for exact matches (status, etc.)
- For aggregations, still include the base search query
- If the query is ambiguous, set needs_clarification=true and ask a specific question
- Handle "last quarter" by calculating previous complete quarter
- Handle "YTD" as year-to-date from Jan 1 to today
- Handle relative dates like "in 30 days" from today forward

Examples:
1. "invoices from Acme over $5000 last quarter"
   → filter vendor (fuzzy match "Acme"), range amount > 5000, date range for Q{current_quarter-1}

2. "total spending by vendor this year"
   → aggregation: group_by vendor, sum amount, date range YTD

3. "find duplicate invoices"
   → anomaly query: group by vendor+amount+date, find count > 1

4. "contracts expiring in 30 days"
   → filter date range from today to today+30 days"""

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
