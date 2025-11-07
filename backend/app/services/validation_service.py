"""
Extraction Validation Service

Validates extracted fields using two approaches:
1. Dynamic Pydantic validation from template schema (NEW)
2. Hardcoded business rules for common templates (EXISTING)

Provides detailed error messages and severity levels (error vs warning).

Usage:
    # With template object (dynamic validation)
    validator = ExtractionValidator()
    results = await validator.validate_extraction(
        extractions={"invoice_number": {"value": "INV-001", "confidence": 0.9}},
        template=template_obj
    )

    # With template name (business rules only)
    results = await validator.validate_extraction(
        extractions={"invoice_number": {"value": "INV-001", "confidence": 0.9}},
        template_name="invoice"
    )
"""

from typing import Dict, Any, List, Optional, Type, Union
from datetime import datetime, timedelta, date
from decimal import Decimal
from dataclasses import dataclass
import logging
import re

from pydantic import BaseModel, Field, create_model, ValidationError, field_validator
from pydantic_core import PydanticCustomError
from sqlalchemy.orm import Session

try:
    from app.models.extraction_schemas import (
        EXTRACTION_SCHEMAS,
        get_validation_schema,
        InvoiceExtraction,
        ContractExtraction,
        ReceiptExtraction,
        PurchaseOrderExtraction
    )
    HAS_EXTRACTION_SCHEMAS = True
except ImportError:
    HAS_EXTRACTION_SCHEMAS = False

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of field validation"""
    status: str  # "valid", "warning", "error"
    errors: List[str]
    warnings: List[str]


class ExtractionValidator:
    """
    Validate extracted fields against business rules

    Features:
    - Dynamic Pydantic validation from template schema (NEW)
    - Template-specific validation using Pydantic models
    - Business logic validation (amounts, dates, etc.)
    - Cross-field validation (date ranges, dependencies)
    - Confidence-adjusted severity (high conf + error = warning)
    """

    # Common regex patterns for format validation
    PATTERNS = {
        'email': r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
        'phone': r'^\+?1?\d{9,15}$',
        'url': r'^https?://[^\s/$.?#].[^\s]*$',
        'postal_code': r'^\d{5}(-\d{4})?$',
        'currency': r'^\$?\d+(,\d{3})*(\.\d{2})?$',
        'date_iso': r'^\d{4}-\d{2}-\d{2}$',
        'time': r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9](:[0-5][0-9])?$',
    }

    def __init__(self):
        self.validation_schemas = EXTRACTION_SCHEMAS if HAS_EXTRACTION_SCHEMAS else {}
        self._model_cache: Dict[int, Type[BaseModel]] = {}

    async def validate_extraction(
        self,
        extractions: Dict[str, Any],
        template: Optional[Any] = None,
        template_name: Optional[str] = None,
        schema_config: Dict[str, Any] = None
    ) -> Dict[str, ValidationResult]:
        """
        Validate all fields in an extraction

        Args:
            extractions: Dict of {field_name: {value, confidence, ...}}
            template: Template object with schema (for dynamic validation)
            template_name: Template name for business rules validation
            schema_config: Optional schema config with required fields

        Returns:
            Dict of {field_name: ValidationResult}
        """
        results = {}

        # If template object provided, use dynamic validation
        if template:
            results = await self._validate_with_dynamic_model(template, extractions)
            template_name = template.name if hasattr(template, 'name') else template_name

        # Also apply field-level validation (business rules + type checking)
        for field_name, field_data in extractions.items():
            # If already validated dynamically, merge results
            if field_name in results:
                existing_result = results[field_name]
                additional_result = await self._validate_field(
                    field_name=field_name,
                    field_data=field_data,
                    template_name=template_name or "",
                    schema_config=schema_config
                )
                # Merge errors and warnings
                existing_result.errors.extend(additional_result.errors)
                existing_result.warnings.extend(additional_result.warnings)
                # Update status to worst case
                if additional_result.status == "error" or existing_result.status == "error":
                    existing_result.status = "error"
                elif additional_result.status == "warning" or existing_result.status == "warning":
                    existing_result.status = "warning"
            else:
                # No dynamic validation, just business rules
                result = await self._validate_field(
                    field_name=field_name,
                    field_data=field_data,
                    template_name=template_name or "",
                    schema_config=schema_config
                )
                results[field_name] = result

        # Cross-field validation
        cross_field_errors = self._validate_cross_field_rules(extractions, template_name or "")
        if cross_field_errors:
            # Add cross-field errors to relevant fields
            for field_name, errors in cross_field_errors.items():
                if field_name in results:
                    results[field_name].errors.extend(errors)
                    if results[field_name].status == "valid":
                        results[field_name].status = "error"

        return results

    async def _validate_with_dynamic_model(
        self,
        template: Any,
        extractions: Dict[str, Any]
    ) -> Dict[str, ValidationResult]:
        """
        Validate extractions using dynamically generated Pydantic model

        Args:
            template: Template object with extraction_fields schema
            extractions: Dict of {field_name: {value, confidence, ...}}

        Returns:
            Dict of {field_name: ValidationResult}
        """
        results = {}

        # Get or create validation model for this template
        validation_model = self._get_validation_model(template)

        # Extract just the values for Pydantic validation
        values_only = {
            field_name: field_data.get("value")
            for field_name, field_data in extractions.items()
        }

        try:
            # Validate using Pydantic model
            validated_instance = validation_model(**values_only)
            validated_data = validated_instance.model_dump()

            # All fields passed validation
            for field_name in values_only.keys():
                confidence = extractions[field_name].get("confidence", 1.0)
                results[field_name] = ValidationResult(
                    status="valid",
                    errors=[],
                    warnings=[]
                )

        except ValidationError as e:
            # Convert Pydantic errors to our format
            for err in e.errors():
                field_name = err['loc'][0] if err['loc'] else 'unknown'
                confidence = extractions.get(field_name, {}).get("confidence", 1.0)

                error_msg = err['msg']
                validation_type = self._get_validation_type(err['type'])

                # Create or update result for this field
                if field_name not in results:
                    results[field_name] = ValidationResult(
                        status="error",
                        errors=[error_msg],
                        warnings=[]
                    )
                else:
                    results[field_name].errors.append(error_msg)
                    results[field_name].status = "error"

                # Adjust status based on confidence
                results[field_name].status = self._determine_status(
                    results[field_name].errors,
                    results[field_name].warnings,
                    confidence
                )

            # Mark non-errored fields as valid
            for field_name in values_only.keys():
                if field_name not in results:
                    results[field_name] = ValidationResult(
                        status="valid",
                        errors=[],
                        warnings=[]
                    )

        return results

    def _get_validation_model(self, template: Any) -> Type[BaseModel]:
        """Get or create a Pydantic validation model for the template."""
        template_id = template.id if hasattr(template, 'id') else 0

        # Check cache first
        if template_id in self._model_cache:
            return self._model_cache[template_id]

        # Create dynamic model
        model = self._create_validation_model(template)
        self._model_cache[template_id] = model
        return model

    def _create_validation_model(self, template: Any) -> Type[BaseModel]:
        """Dynamically create a Pydantic model from template schema."""
        fields = {}
        validators_dict = {}

        extraction_fields = template.extraction_fields if hasattr(template, 'extraction_fields') else []

        for field_def in extraction_fields:
            field_name = field_def['name']
            field_type = self._get_pydantic_type(field_def)
            field_kwargs = self._get_field_kwargs(field_def)

            fields[field_name] = (field_type, Field(**field_kwargs))

        # Create model class dynamically
        model_name = f'{template.name.replace(" ", "_")}_ValidationModel'
        model = create_model(model_name, **fields)

        return model

    def _get_pydantic_type(self, field_def: Dict[str, Any]) -> Any:
        """Map template field types to Pydantic types."""
        field_type = field_def.get('type', 'text')
        validation = field_def.get('validation', {})
        required = validation.get('required', False)

        # Base type mapping
        type_map = {
            'text': str,
            'number': Union[int, float],
            'date': Union[date, str],  # Accept both date objects and ISO strings
            'boolean': bool,
            'array': List[str],
            'table': List[Dict[str, Any]],
            'array_of_objects': List[Dict[str, Any]]
        }

        base_type = type_map.get(field_type, str)

        # Make optional if not required
        if not required:
            return Optional[base_type]

        return base_type

    def _get_field_kwargs(self, field_def: Dict[str, Any]) -> Dict[str, Any]:
        """Get Pydantic Field kwargs from field definition."""
        validation = field_def.get('validation', {})
        kwargs = {
            'description': field_def.get('description', ''),
        }

        # Default value
        if not validation.get('required', False):
            kwargs['default'] = None

        # Min/max for numbers
        if field_def.get('type') == 'number':
            if 'min' in validation:
                kwargs['ge'] = validation['min']
            if 'max' in validation:
                kwargs['le'] = validation['max']

        # Length constraints for strings
        if field_def.get('type') == 'text':
            if 'min_length' in validation:
                kwargs['min_length'] = validation['min_length']
            if 'max_length' in validation:
                kwargs['max_length'] = validation['max_length']

        # Pattern for strings
        if 'pattern' in validation:
            kwargs['pattern'] = validation['pattern']

        return kwargs

    def _get_validation_type(self, pydantic_error_type: str) -> str:
        """Map Pydantic error types to our validation types."""
        type_map = {
            'string_type': 'type',
            'int_type': 'type',
            'float_type': 'type',
            'bool_type': 'type',
            'date_type': 'type',
            'list_type': 'type',
            'dict_type': 'type',
            'string_pattern_mismatch': 'pattern',
            'string_too_short': 'range',
            'string_too_long': 'range',
            'greater_than_equal': 'range',
            'less_than_equal': 'range',
            'format_error': 'format',
            'missing': 'required',
        }
        return type_map.get(pydantic_error_type, 'custom')

    async def _validate_field(
        self,
        field_name: str,
        field_data: Dict[str, Any],
        template_name: str,
        schema_config: Dict[str, Any] = None
    ) -> ValidationResult:
        """
        Validate a single field

        Args:
            field_name: Name of the field
            field_data: Dict with {value, confidence, ...}
            template_name: Template name
            schema_config: Optional schema config

        Returns:
            ValidationResult with status and errors
        """
        errors = []
        warnings = []

        value = field_data.get("value")
        confidence = field_data.get("confidence", 1.0)

        # Skip validation if value is None or empty
        if value is None or (isinstance(value, str) and value.strip() == ""):
            # Check if field is required
            if schema_config:
                field_config = self._get_field_config(field_name, schema_config)
                if field_config and field_config.get("required"):
                    errors.append(f"Required field '{field_name}' is missing or empty")
            return ValidationResult(
                status="error" if errors else "valid",
                errors=errors,
                warnings=warnings
            )

        # Get Pydantic validation schema
        validation_schema = get_validation_schema(template_name)

        if validation_schema:
            # Try Pydantic validation
            pydantic_errors = self._validate_with_pydantic(
                field_name=field_name,
                value=value,
                validation_schema=validation_schema
            )
            errors.extend(pydantic_errors)

        # Business rules validation (template-specific)
        business_errors = await self._validate_business_rules(
            field_name=field_name,
            value=value,
            template_name=template_name
        )
        errors.extend(business_errors)

        # Type validation
        type_errors = self._validate_field_type(
            field_name=field_name,
            value=value,
            expected_type=self._infer_field_type(field_name)
        )
        errors.extend(type_errors)

        # Determine severity based on confidence
        status = self._determine_status(errors, warnings, confidence)

        return ValidationResult(
            status=status,
            errors=errors,
            warnings=warnings
        )

    def _validate_with_pydantic(
        self,
        field_name: str,
        value: Any,
        validation_schema: type
    ) -> List[str]:
        """
        Validate field using Pydantic model

        Returns:
            List of error messages
        """
        errors = []

        try:
            # Build a minimal dict for Pydantic validation
            # This is tricky because we're validating individual fields
            # For now, we'll use field validators directly if available

            # Check if the validation schema has a validator for this field
            field_info = validation_schema.model_fields.get(field_name)
            if not field_info:
                return errors  # No validation defined for this field

            # Try to validate the type
            try:
                # Attempt type conversion/validation
                if field_info.annotation:
                    # This is simplified - in production you'd use Pydantic's validation properly
                    pass
            except Exception as e:
                errors.append(f"Type validation failed: {str(e)}")

        except Exception as e:
            logger.debug(f"Pydantic validation error for {field_name}: {e}")

        return errors

    async def _validate_business_rules(
        self,
        field_name: str,
        value: Any,
        template_name: str
    ) -> List[str]:
        """
        Apply template-specific business logic validation

        Args:
            field_name: Field name
            value: Field value
            template_name: Template name

        Returns:
            List of error messages
        """
        errors = []

        template_lower = template_name.lower()

        # Invoice-specific rules
        if template_lower == "invoice":
            errors.extend(self._validate_invoice_field(field_name, value))

        # Contract-specific rules
        elif template_lower == "contract":
            errors.extend(self._validate_contract_field(field_name, value))

        # Receipt-specific rules
        elif template_lower == "receipt":
            errors.extend(self._validate_receipt_field(field_name, value))

        # Purchase Order-specific rules
        elif template_lower in ["purchase_order", "purchase order", "po"]:
            errors.extend(self._validate_po_field(field_name, value))

        return errors

    def _validate_invoice_field(self, field_name: str, value: Any) -> List[str]:
        """Invoice-specific field validation"""
        errors = []

        if field_name == "total_amount":
            try:
                amount = float(value) if value is not None else 0
                if amount <= 0:
                    errors.append("Invoice total must be positive")
                if amount > 1_000_000:
                    errors.append("Invoice total exceeds $1M - flagged for review")
            except (ValueError, TypeError):
                errors.append("Invalid amount format")

        elif field_name == "invoice_date":
            try:
                if isinstance(value, str):
                    date_val = datetime.fromisoformat(value).date()
                elif isinstance(value, datetime):
                    date_val = value.date()
                else:
                    date_val = value

                today = datetime.now().date()
                if date_val > today + timedelta(days=30):
                    errors.append("Invoice date is more than 30 days in the future")
                if date_val < today - timedelta(days=5*365):
                    errors.append("Invoice date is more than 5 years in the past")
            except (ValueError, TypeError):
                errors.append("Invalid date format")

        elif field_name == "invoice_number":
            if not value or (isinstance(value, str) and not value.strip()):
                errors.append("Invoice number cannot be empty")

        return errors

    def _validate_contract_field(self, field_name: str, value: Any) -> List[str]:
        """Contract-specific field validation"""
        errors = []

        if field_name == "contract_value":
            try:
                if value is not None:
                    amount = float(value)
                    if amount <= 0:
                        errors.append("Contract value must be positive")
            except (ValueError, TypeError):
                errors.append("Invalid contract value format")

        elif field_name == "parties":
            if isinstance(value, list) and len(value) < 2:
                errors.append("Contract must have at least 2 parties")

        return errors

    def _validate_receipt_field(self, field_name: str, value: Any) -> List[str]:
        """Receipt-specific field validation"""
        errors = []

        if field_name == "total_amount":
            try:
                amount = float(value) if value is not None else 0
                if amount <= 0:
                    errors.append("Receipt total must be positive")
                if amount > 50_000:
                    errors.append("Receipt total exceeds $50k - flagged for review")
            except (ValueError, TypeError):
                errors.append("Invalid amount format")

        elif field_name == "receipt_date":
            try:
                if isinstance(value, str):
                    date_val = datetime.fromisoformat(value).date()
                else:
                    date_val = value

                today = datetime.now().date()
                if date_val > today:
                    errors.append("Receipt date cannot be in the future")
            except (ValueError, TypeError):
                errors.append("Invalid date format")

        return errors

    def _validate_po_field(self, field_name: str, value: Any) -> List[str]:
        """Purchase Order-specific field validation"""
        errors = []

        if field_name == "total_amount":
            try:
                amount = float(value) if value is not None else 0
                if amount <= 0:
                    errors.append("PO total must be positive")
            except (ValueError, TypeError):
                errors.append("Invalid amount format")

        return errors

    def _validate_cross_field_rules(
        self,
        extractions: Dict[str, Any],
        template_name: str
    ) -> Dict[str, List[str]]:
        """
        Validate relationships between fields

        Args:
            extractions: All extracted fields
            template_name: Template name

        Returns:
            Dict of {field_name: [errors]}
        """
        errors_by_field = {}
        template_lower = template_name.lower()

        # Invoice: due_date after invoice_date
        if template_lower == "invoice":
            if "invoice_date" in extractions and "due_date" in extractions:
                try:
                    inv_date = extractions["invoice_date"]["value"]
                    due_date = extractions["due_date"]["value"]

                    if isinstance(inv_date, str):
                        inv_date = datetime.fromisoformat(inv_date).date()
                    if isinstance(due_date, str):
                        due_date = datetime.fromisoformat(due_date).date()

                    if due_date < inv_date:
                        errors_by_field["due_date"] = ["Due date must be after invoice date"]
                except Exception:
                    pass

        # Contract: expiration_date after effective_date
        elif template_lower == "contract":
            if "effective_date" in extractions and "expiration_date" in extractions:
                try:
                    eff_date = extractions["effective_date"]["value"]
                    exp_date = extractions["expiration_date"]["value"]

                    if isinstance(eff_date, str):
                        eff_date = datetime.fromisoformat(eff_date).date()
                    if isinstance(exp_date, str):
                        exp_date = datetime.fromisoformat(exp_date).date()

                    if exp_date <= eff_date:
                        errors_by_field["expiration_date"] = ["Expiration date must be after effective date"]
                except Exception:
                    pass

        return errors_by_field

    def _validate_field_type(
        self,
        field_name: str,
        value: Any,
        expected_type: str
    ) -> List[str]:
        """
        Validate field has correct type

        Args:
            field_name: Field name
            value: Field value
            expected_type: Expected type (date, number, text, etc.)

        Returns:
            List of error messages
        """
        errors = []

        if expected_type == "date":
            try:
                if isinstance(value, str):
                    datetime.fromisoformat(value)
            except ValueError:
                errors.append(f"Field '{field_name}' has invalid date format")

        elif expected_type == "number":
            try:
                float(value)
            except (ValueError, TypeError):
                errors.append(f"Field '{field_name}' must be a number")

        return errors

    def _infer_field_type(self, field_name: str) -> str:
        """Infer expected type from field name"""
        if "date" in field_name.lower():
            return "date"
        elif "amount" in field_name.lower() or "total" in field_name.lower() or "value" in field_name.lower():
            return "number"
        else:
            return "text"

    def _determine_status(
        self,
        errors: List[str],
        warnings: List[str],
        confidence: float
    ) -> str:
        """
        Determine validation status based on errors and confidence

        High confidence + errors → warning (might be false positive)
        Low confidence + errors → error (likely correct)
        No errors → valid

        Args:
            errors: List of error messages
            warnings: List of warning messages
            confidence: Confidence score (0-1)

        Returns:
            "valid", "warning", or "error"
        """
        if not errors and not warnings:
            return "valid"

        if errors:
            # If confidence is high (>=0.8), downgrade to warning
            # The extraction might be correct despite validation failure
            if confidence >= 0.8:
                return "warning"
            else:
                return "error"

        if warnings:
            return "warning"

        return "valid"

    def _get_field_config(self, field_name: str, schema_config: Dict[str, Any]) -> Dict[str, Any]:
        """Get field configuration from schema"""
        if not schema_config or "fields" not in schema_config:
            return {}

        for field in schema_config.get("fields", []):
            if field.get("name") == field_name:
                return field

        return {}


def should_flag_for_review(confidence: float, validation_status: str) -> bool:
    """
    Determine if a field should be flagged for human review

    Args:
        confidence: Confidence score (0-1)
        validation_status: "valid", "warning", or "error"

    Returns:
        True if field needs review
    """
    # Always flag validation errors
    if validation_status == "error":
        return True

    # Flag low confidence
    if confidence < 0.6:
        return True

    # Flag medium confidence with validation warning
    if confidence < 0.8 and validation_status == "warning":
        return True

    return False
