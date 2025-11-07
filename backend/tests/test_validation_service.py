"""
Tests for extraction validation service.

Tests dynamic Pydantic model generation, validation rules,
and integration with extraction pipeline.
"""

import pytest
from datetime import datetime, date
from app.services.validation_service import ExtractionValidator, ValidationResult, should_flag_for_review


class MockTemplate:
    """Mock template for testing dynamic validation"""

    def __init__(self, name: str, extraction_fields: list):
        self.id = 1
        self.name = name
        self.extraction_fields = extraction_fields


@pytest.fixture
def validator():
    """Create validator instance"""
    return ExtractionValidator()


@pytest.fixture
def invoice_template():
    """Mock invoice template with validation rules"""
    return MockTemplate(
        name="Invoice",
        extraction_fields=[
            {
                "name": "invoice_number",
                "type": "text",
                "description": "Invoice number",
                "validation": {
                    "required": True,
                    "pattern": r"^INV-\d{6}$",
                    "min_length": 5,
                    "max_length": 20
                }
            },
            {
                "name": "total_amount",
                "type": "number",
                "description": "Total invoice amount",
                "validation": {
                    "required": True,
                    "min": 0,
                    "max": 1000000
                }
            },
            {
                "name": "invoice_date",
                "type": "date",
                "description": "Invoice date",
                "validation": {
                    "required": True
                }
            },
            {
                "name": "vendor_email",
                "type": "text",
                "description": "Vendor email",
                "validation": {
                    "format": "email"
                }
            },
            {
                "name": "notes",
                "type": "text",
                "description": "Optional notes",
                "validation": {
                    "required": False,
                    "max_length": 500
                }
            }
        ]
    )


class TestDynamicModelGeneration:
    """Test dynamic Pydantic model generation from template schemas"""

    @pytest.mark.asyncio
    async def test_create_validation_model(self, validator, invoice_template):
        """Test creating a Pydantic model from template schema"""
        model = validator._get_validation_model(invoice_template)

        assert model is not None
        assert "Invoice" in model.__name__
        assert "invoice_number" in model.model_fields
        assert "total_amount" in model.model_fields
        assert "invoice_date" in model.model_fields

    @pytest.mark.asyncio
    async def test_model_caching(self, validator, invoice_template):
        """Test that validation models are cached"""
        model1 = validator._get_validation_model(invoice_template)
        model2 = validator._get_validation_model(invoice_template)

        assert model1 is model2  # Same object (cached)

    @pytest.mark.asyncio
    async def test_type_mapping(self, validator):
        """Test field type mapping to Pydantic types"""
        # Text field
        text_field = {"name": "test", "type": "text", "validation": {"required": True}}
        pydantic_type = validator._get_pydantic_type(text_field)
        assert pydantic_type == str

        # Number field
        number_field = {"name": "test", "type": "number", "validation": {"required": True}}
        pydantic_type = validator._get_pydantic_type(number_field)
        # Should be Union[int, float]
        assert hasattr(pydantic_type, '__origin__')

        # Optional field
        optional_field = {"name": "test", "type": "text", "validation": {"required": False}}
        pydantic_type = validator._get_pydantic_type(optional_field)
        # Should be Optional[str]
        assert hasattr(pydantic_type, '__origin__')


class TestFieldValidation:
    """Test validation of individual fields"""

    @pytest.mark.asyncio
    async def test_valid_extraction(self, validator, invoice_template):
        """Test validation passes for valid data"""
        extractions = {
            "invoice_number": {"value": "INV-123456", "confidence": 0.95},
            "total_amount": {"value": 1500.50, "confidence": 0.90},
            "invoice_date": {"value": "2025-01-15", "confidence": 0.85},
            "vendor_email": {"value": "vendor@example.com", "confidence": 0.80},
            "notes": {"value": "Test notes", "confidence": 0.75}
        }

        results = await validator.validate_extraction(
            extractions=extractions,
            template=invoice_template
        )

        # All fields should be valid
        assert all(r.status == "valid" for r in results.values())
        assert all(len(r.errors) == 0 for r in results.values())

    @pytest.mark.asyncio
    async def test_required_field_missing(self, validator, invoice_template):
        """Test validation fails when required field is missing"""
        extractions = {
            "invoice_number": {"value": None, "confidence": 0.3},  # Required but missing
            "total_amount": {"value": 1500.50, "confidence": 0.90}
        }

        results = await validator.validate_extraction(
            extractions=extractions,
            template=invoice_template
        )

        # invoice_number should have error
        assert "invoice_number" in results
        assert results["invoice_number"].status in ["error", "warning"]
        assert len(results["invoice_number"].errors) > 0

    @pytest.mark.asyncio
    async def test_pattern_validation(self, validator, invoice_template):
        """Test pattern validation for text fields"""
        extractions = {
            "invoice_number": {"value": "INVALID-123", "confidence": 0.6},  # Doesn't match pattern
            "total_amount": {"value": 100, "confidence": 0.9}
        }

        results = await validator.validate_extraction(
            extractions=extractions,
            template=invoice_template
        )

        # invoice_number should fail pattern validation
        assert "invoice_number" in results
        assert results["invoice_number"].status in ["error", "warning"]

    @pytest.mark.asyncio
    async def test_range_validation(self, validator, invoice_template):
        """Test min/max validation for numbers"""
        # Test exceeds max
        extractions_high = {
            "invoice_number": {"value": "INV-123456", "confidence": 0.9},
            "total_amount": {"value": 2000000, "confidence": 0.8},  # Exceeds max (1000000)
        }

        results_high = await validator.validate_extraction(
            extractions=extractions_high,
            template=invoice_template
        )

        assert "total_amount" in results_high
        assert results_high["total_amount"].status in ["error", "warning"]

        # Test below min
        extractions_low = {
            "invoice_number": {"value": "INV-123456", "confidence": 0.9},
            "total_amount": {"value": -100, "confidence": 0.8},  # Below min (0)
        }

        results_low = await validator.validate_extraction(
            extractions=extractions_low,
            template=invoice_template
        )

        assert "total_amount" in results_low
        assert results_low["total_amount"].status in ["error", "warning"]

    @pytest.mark.asyncio
    async def test_length_validation(self, validator, invoice_template):
        """Test string length validation"""
        extractions = {
            "invoice_number": {"value": "INV-123456", "confidence": 0.9},
            "total_amount": {"value": 100, "confidence": 0.9},
            "notes": {"value": "x" * 600, "confidence": 0.8}  # Exceeds max_length (500)
        }

        results = await validator.validate_extraction(
            extractions=extractions,
            template=invoice_template
        )

        assert "notes" in results
        assert results["notes"].status in ["error", "warning"]


class TestBusinessRulesValidation:
    """Test template-specific business rules"""

    @pytest.mark.asyncio
    async def test_invoice_business_rules(self, validator):
        """Test invoice-specific business rules"""
        extractions = {
            "invoice_number": {"value": None, "confidence": 0.3},  # Missing invoice number
            "total_amount": {"value": -100, "confidence": 0.8},  # Negative amount
            "invoice_date": {"value": "2030-01-01", "confidence": 0.7}  # Future date
        }

        results = await validator.validate_extraction(
            extractions=extractions,
            template_name="invoice"
        )

        # Should have validation errors for business rules
        # invoice_number may pass if not required by business rules, but others should fail
        assert results["total_amount"].status in ["error", "warning"]
        assert results["invoice_date"].status in ["error", "warning"]

    @pytest.mark.asyncio
    async def test_contract_business_rules(self, validator):
        """Test contract-specific business rules"""
        extractions = {
            "contract_value": {"value": -5000, "confidence": 0.8},  # Negative value
            "parties": {"value": ["Party A"], "confidence": 0.9}  # Only 1 party (need 2+)
        }

        results = await validator.validate_extraction(
            extractions=extractions,
            template_name="contract"
        )

        assert results["contract_value"].status in ["error", "warning"]
        assert results["parties"].status in ["error", "warning"]


class TestCrossFieldValidation:
    """Test validation rules that span multiple fields"""

    @pytest.mark.asyncio
    async def test_invoice_date_range(self, validator):
        """Test that due_date is after invoice_date"""
        extractions = {
            "invoice_date": {"value": "2025-02-01", "confidence": 0.9},
            "due_date": {"value": "2025-01-01", "confidence": 0.8}  # Before invoice date!
        }

        results = await validator.validate_extraction(
            extractions=extractions,
            template_name="invoice"
        )

        # due_date should have cross-field validation error
        assert "due_date" in results
        assert results["due_date"].status in ["error", "warning"]
        assert any("after invoice date" in str(err).lower() for err in results["due_date"].errors)

    @pytest.mark.asyncio
    async def test_contract_date_range(self, validator):
        """Test that expiration_date is after effective_date"""
        extractions = {
            "effective_date": {"value": "2025-01-01", "confidence": 0.9},
            "expiration_date": {"value": "2024-12-31", "confidence": 0.8}  # Before effective!
        }

        results = await validator.validate_extraction(
            extractions=extractions,
            template_name="contract"
        )

        assert "expiration_date" in results
        assert results["expiration_date"].status in ["error", "warning"]


class TestConfidenceAdjustment:
    """Test severity adjustment based on confidence scores"""

    @pytest.mark.asyncio
    async def test_high_confidence_downgrade(self, validator):
        """Test that high confidence + error = warning (might be false positive)"""
        extractions = {
            "invoice_number": {"value": "WRONG-123", "confidence": 0.95},  # High conf, bad format
        }

        # Create minimal template
        template = MockTemplate(
            name="Test",
            extraction_fields=[{
                "name": "invoice_number",
                "type": "text",
                "validation": {"pattern": r"^INV-\d{6}$"}
            }]
        )

        results = await validator.validate_extraction(
            extractions=extractions,
            template=template
        )

        # High confidence should downgrade error to warning
        assert results["invoice_number"].status == "warning"

    @pytest.mark.asyncio
    async def test_low_confidence_error(self, validator):
        """Test that low confidence + error = error (likely correct)"""
        extractions = {
            "invoice_number": {"value": "WRONG-123", "confidence": 0.3},  # Low conf, bad format
        }

        template = MockTemplate(
            name="Test",
            extraction_fields=[{
                "name": "invoice_number",
                "type": "text",
                "validation": {"pattern": r"^INV-\d{6}$"}
            }]
        )

        results = await validator.validate_extraction(
            extractions=extractions,
            template=template
        )

        # Low confidence should keep error as error
        assert results["invoice_number"].status == "error"


class TestReviewFlagging:
    """Test should_flag_for_review function"""

    def test_flag_validation_errors(self):
        """Always flag validation errors"""
        assert should_flag_for_review(confidence=0.95, validation_status="error") == True
        assert should_flag_for_review(confidence=0.5, validation_status="error") == True

    def test_flag_low_confidence(self):
        """Flag low confidence extractions"""
        assert should_flag_for_review(confidence=0.3, validation_status="valid") == True
        assert should_flag_for_review(confidence=0.5, validation_status="valid") == True

    def test_flag_medium_confidence_with_warning(self):
        """Flag medium confidence with validation warning"""
        assert should_flag_for_review(confidence=0.7, validation_status="warning") == True

    def test_dont_flag_high_confidence_valid(self):
        """Don't flag high confidence valid extractions"""
        assert should_flag_for_review(confidence=0.95, validation_status="valid") == False
        assert should_flag_for_review(confidence=0.85, validation_status="valid") == False


class TestComplexDataTypes:
    """Test validation of complex field types (arrays, tables)"""

    @pytest.mark.asyncio
    async def test_array_validation(self, validator):
        """Test validation of array fields"""
        template = MockTemplate(
            name="Test",
            extraction_fields=[{
                "name": "tags",
                "type": "array",
                "description": "Document tags",
                "validation": {"required": True}
            }]
        )

        # Valid array
        extractions_valid = {
            "tags": {"value": ["urgent", "invoice", "approved"], "confidence": 0.9}
        }

        results_valid = await validator.validate_extraction(
            extractions=extractions_valid,
            template=template
        )

        assert results_valid["tags"].status == "valid"

        # Missing required array
        extractions_missing = {
            "tags": {"value": None, "confidence": 0.3}
        }

        results_missing = await validator.validate_extraction(
            extractions=extractions_missing,
            template=template
        )

        assert results_missing["tags"].status in ["error", "warning"]

    @pytest.mark.asyncio
    async def test_table_validation(self, validator):
        """Test validation of table (array_of_objects) fields"""
        template = MockTemplate(
            name="Test",
            extraction_fields=[{
                "name": "line_items",
                "type": "array_of_objects",
                "description": "Invoice line items",
                "validation": {"required": False}
            }]
        )

        # Valid table
        extractions = {
            "line_items": {
                "value": [
                    {"item": "Widget", "qty": 5, "price": 10.00},
                    {"item": "Gadget", "qty": 3, "price": 25.00}
                ],
                "confidence": 0.85
            }
        }

        results = await validator.validate_extraction(
            extractions=extractions,
            template=template
        )

        assert results["line_items"].status == "valid"


class TestIntegration:
    """Integration tests with extraction service"""

    @pytest.mark.asyncio
    async def test_validation_in_extraction_flow(self, validator, invoice_template):
        """Test validation integrates with extraction pipeline"""
        # Simulate extraction result from Reducto
        extracted_data = {
            "invoice_number": "INV-123456",
            "total_amount": 1500.50,
            "invoice_date": "2025-01-15",
            "vendor_email": "vendor@example.com"
        }

        confidence_scores = {
            "invoice_number": 0.95,
            "total_amount": 0.90,
            "invoice_date": 0.85,
            "vendor_email": 0.55  # Low confidence (below 0.6 threshold)
        }

        # Prepare for validation
        extractions = {
            field_name: {
                "value": field_value,
                "confidence": confidence_scores.get(field_name, 0.0)
            }
            for field_name, field_value in extracted_data.items()
        }

        # Run validation
        results = await validator.validate_extraction(
            extractions=extractions,
            template=invoice_template
        )

        # Check results
        assert len(results) == 4
        assert all(field in results for field in extracted_data.keys())

        # vendor_email should be flagged for review (low confidence)
        assert should_flag_for_review(
            confidence_scores["vendor_email"],
            results["vendor_email"].status
        ) == True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
