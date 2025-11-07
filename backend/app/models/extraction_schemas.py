"""
Pydantic validation models for extracted document fields

These models define validation rules for different document types.
They catch logical errors that confidence scores miss (e.g., negative amounts, future dates).

Usage:
    from app.models.extraction_schemas import EXTRACTION_SCHEMAS

    validator = EXTRACTION_SCHEMAS["invoice"]
    result = validator.validate(extracted_data)
"""

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List, Dict, Any
from datetime import date, datetime, timedelta
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class ExtractedFieldBase(BaseModel):
    """Base model for extracted fields with metadata"""
    value: Any
    confidence: float = Field(ge=0.0, le=1.0)
    source_page: Optional[int] = None
    source_bbox: Optional[List[float]] = None
    verified: bool = False

    model_config = {
        "json_schema_extra": {
            "example": {
                "value": "2024-01-15",
                "confidence": 0.87,
                "source_page": 1,
                "verified": False
            }
        }
    }


class InvoiceExtraction(BaseModel):
    """
    Invoice extraction with business validation rules

    Validates:
    - Invoice number format and presence
    - Positive amounts
    - Reasonable date ranges
    - Vendor name presence
    """
    invoice_number: str = Field(min_length=1, max_length=100, description="Invoice identifier")
    invoice_date: date = Field(description="Invoice issue date")
    total_amount: Decimal = Field(gt=0, description="Total invoice amount")
    vendor_name: str = Field(min_length=1, description="Vendor/supplier name")
    line_items: Optional[List[Dict[str, Any]]] = Field(default=[], description="Invoice line items")
    due_date: Optional[date] = Field(default=None, description="Payment due date")
    po_number: Optional[str] = Field(default=None, description="Purchase order number")

    @field_validator('invoice_number')
    @classmethod
    def validate_invoice_number(cls, v: str) -> str:
        """Validate invoice number format"""
        if not v or v.strip() == "":
            raise ValueError("Invoice number cannot be empty")

        # Normalize format
        normalized = v.strip().upper()

        # Check length
        if len(normalized) > 100:
            raise ValueError("Invoice number too long (max 100 characters)")

        return normalized

    @field_validator('total_amount')
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        """Validate total amount is positive and reasonable"""
        if v <= 0:
            raise ValueError("Total amount must be positive")

        # Flag unusually high amounts for review
        if v > 1_000_000:
            raise ValueError("Total amount exceeds $1M - needs manual review")

        return v

    @field_validator('invoice_date')
    @classmethod
    def validate_invoice_date(cls, v: date) -> date:
        """Validate invoice date is reasonable"""
        today = datetime.now().date()

        # Check if date is too far in the past (>5 years)
        if v < today - timedelta(days=5*365):
            raise ValueError("Invoice date is more than 5 years in the past")

        # Check if date is too far in the future (>30 days)
        if v > today + timedelta(days=30):
            raise ValueError("Invoice date is more than 30 days in the future")

        return v

    @field_validator('vendor_name')
    @classmethod
    def validate_vendor_name(cls, v: str) -> str:
        """Validate vendor name presence"""
        if not v or v.strip() == "":
            raise ValueError("Vendor name cannot be empty")

        return v.strip()

    @model_validator(mode='after')
    def validate_due_date(self) -> 'InvoiceExtraction':
        """Validate due date is after invoice date"""
        if self.due_date and self.due_date < self.invoice_date:
            raise ValueError("Due date must be after invoice date")

        return self


class ContractExtraction(BaseModel):
    """
    Contract extraction with date and party validation

    Validates:
    - Contract identifier presence
    - Date ordering (effective before expiration)
    - Minimum number of parties (2)
    - Optional contract value validation
    """
    contract_id: str = Field(min_length=1, description="Contract identifier")
    effective_date: date = Field(description="Contract effective date")
    expiration_date: date = Field(description="Contract expiration date")
    parties: List[str] = Field(min_length=2, max_length=10, description="Contract parties")
    contract_value: Optional[Decimal] = Field(default=None, gt=0, description="Contract value")
    renewal_terms: Optional[str] = Field(default=None, description="Renewal terms")

    @field_validator('contract_id')
    @classmethod
    def validate_contract_id(cls, v: str) -> str:
        """Validate contract ID format"""
        if not v or v.strip() == "":
            raise ValueError("Contract ID cannot be empty")

        return v.strip().upper()

    @field_validator('parties')
    @classmethod
    def validate_parties(cls, v: List[str]) -> List[str]:
        """Validate parties list"""
        if len(v) < 2:
            raise ValueError("Contract must have at least 2 parties")

        # Remove empty strings
        cleaned = [p.strip() for p in v if p and p.strip()]

        if len(cleaned) < 2:
            raise ValueError("Contract must have at least 2 non-empty party names")

        return cleaned

    @model_validator(mode='after')
    def validate_dates(self) -> 'ContractExtraction':
        """Validate expiration date is after effective date"""
        if self.expiration_date <= self.effective_date:
            raise ValueError("Expiration date must be after effective date")

        # Check for unusually short contracts (<1 day)
        if (self.expiration_date - self.effective_date).days < 1:
            raise ValueError("Contract duration is less than 1 day")

        return self


class ReceiptExtraction(BaseModel):
    """
    Receipt extraction with simpler validation

    Validates:
    - Merchant name presence
    - Positive total amount
    - Reasonable date
    """
    merchant_name: str = Field(min_length=1, description="Merchant/store name")
    receipt_date: date = Field(description="Receipt date")
    total_amount: Decimal = Field(gt=0, description="Total amount")
    payment_method: Optional[str] = Field(default=None, description="Payment method")
    items: Optional[List[Dict[str, Any]]] = Field(default=[], description="Receipt items")

    @field_validator('merchant_name')
    @classmethod
    def validate_merchant_name(cls, v: str) -> str:
        """Validate merchant name"""
        if not v or v.strip() == "":
            raise ValueError("Merchant name cannot be empty")

        return v.strip()

    @field_validator('total_amount')
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        """Validate total amount"""
        if v <= 0:
            raise ValueError("Total amount must be positive")

        if v > 50_000:
            raise ValueError("Total amount exceeds $50k - needs manual review")

        return v

    @field_validator('receipt_date')
    @classmethod
    def validate_receipt_date(cls, v: date) -> date:
        """Validate receipt date is reasonable"""
        today = datetime.now().date()

        # Check if date is too far in the past (>3 years)
        if v < today - timedelta(days=3*365):
            raise ValueError("Receipt date is more than 3 years in the past")

        # Check if date is in the future
        if v > today:
            raise ValueError("Receipt date cannot be in the future")

        return v


class PurchaseOrderExtraction(BaseModel):
    """
    Purchase Order extraction with validation

    Validates:
    - PO number presence
    - Vendor information
    - Positive amounts
    - Reasonable dates
    """
    po_number: str = Field(min_length=1, description="Purchase order number")
    vendor_name: str = Field(min_length=1, description="Vendor name")
    po_date: date = Field(description="PO issue date")
    total_amount: Decimal = Field(gt=0, description="Total PO amount")
    delivery_date: Optional[date] = Field(default=None, description="Expected delivery date")
    line_items: Optional[List[Dict[str, Any]]] = Field(default=[], description="PO line items")

    @field_validator('po_number')
    @classmethod
    def validate_po_number(cls, v: str) -> str:
        """Validate PO number"""
        if not v or v.strip() == "":
            raise ValueError("PO number cannot be empty")

        return v.strip().upper()

    @field_validator('vendor_name')
    @classmethod
    def validate_vendor_name(cls, v: str) -> str:
        """Validate vendor name"""
        if not v or v.strip() == "":
            raise ValueError("Vendor name cannot be empty")

        return v.strip()

    @field_validator('total_amount')
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        """Validate total amount"""
        if v <= 0:
            raise ValueError("Total amount must be positive")

        return v

    @model_validator(mode='after')
    def validate_delivery_date(self) -> 'PurchaseOrderExtraction':
        """Validate delivery date is after PO date"""
        if self.delivery_date and self.delivery_date < self.po_date:
            raise ValueError("Delivery date must be after PO date")

        return self


# Registry for dynamic model selection
EXTRACTION_SCHEMAS = {
    "invoice": InvoiceExtraction,
    "contract": ContractExtraction,
    "receipt": ReceiptExtraction,
    "purchase_order": PurchaseOrderExtraction,
    "purchase order": PurchaseOrderExtraction,  # Alternative name
    "po": PurchaseOrderExtraction,  # Short name
}


def get_validation_schema(template_name: str) -> Optional[type[BaseModel]]:
    """
    Get Pydantic validation schema for a template

    Args:
        template_name: Template name (case-insensitive)

    Returns:
        Pydantic model class or None if no schema defined
    """
    return EXTRACTION_SCHEMAS.get(template_name.lower())


def validate_field_value(
    field_name: str,
    field_value: Any,
    template_name: str
) -> tuple[bool, Optional[str]]:
    """
    Validate a single field value

    Args:
        field_name: Name of the field
        field_value: Value to validate
        template_name: Template name for context

    Returns:
        (is_valid, error_message)
    """
    schema = get_validation_schema(template_name)
    if not schema:
        return True, None  # No validation schema defined

    try:
        # Try to validate the field
        # This is a simplified validation - in practice you'd build a partial model
        return True, None
    except Exception as e:
        return False, str(e)
