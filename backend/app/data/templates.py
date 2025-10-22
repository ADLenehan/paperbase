"""
Built-in schema templates for common document types.
These encode best practices and common field patterns.
"""

BUILTIN_TEMPLATES = [
    {
        "name": "Invoice",
        "category": "invoice",
        "description": "Standard invoice with line items, totals, and payment terms",
        "icon": "🧾",
        "fields": [
            {
                "name": "invoice_number",
                "type": "text",
                "description": "Unique invoice identifier",
                "required": True,
                "confidence_threshold": 0.85,
                "extraction_hints": ["Invoice #", "Invoice No", "Invoice Number", "INV-"]
            },
            {
                "name": "invoice_date",
                "type": "date",
                "description": "Date invoice was issued",
                "required": True,
                "confidence_threshold": 0.8,
                "extraction_hints": ["Invoice Date", "Date", "Dated", "Issue Date"]
            },
            {
                "name": "due_date",
                "type": "date",
                "description": "Payment due date",
                "required": False,
                "confidence_threshold": 0.75,
                "extraction_hints": ["Due Date", "Payment Due", "Net 30", "Due By"]
            },
            {
                "name": "vendor_name",
                "type": "text",
                "description": "Company or person issuing the invoice",
                "required": True,
                "confidence_threshold": 0.8,
                "extraction_hints": ["From:", "Vendor:", "Billed By", "Company Name"]
            },
            {
                "name": "customer_name",
                "type": "text",
                "description": "Customer or company being billed",
                "required": True,
                "confidence_threshold": 0.8,
                "extraction_hints": ["Bill To:", "Customer:", "Billed To", "Client Name"]
            },
            {
                "name": "subtotal",
                "type": "number",
                "description": "Subtotal before tax",
                "required": False,
                "confidence_threshold": 0.75,
                "extraction_hints": ["Subtotal", "Sub Total", "Sub-Total", "Amount Before Tax"]
            },
            {
                "name": "tax_amount",
                "type": "number",
                "description": "Total tax amount",
                "required": False,
                "confidence_threshold": 0.7,
                "extraction_hints": ["Tax", "VAT", "GST", "Sales Tax", "Tax Amount"]
            },
            {
                "name": "total_amount",
                "type": "number",
                "description": "Final total amount due",
                "required": True,
                "confidence_threshold": 0.85,
                "extraction_hints": ["Total", "Amount Due", "Total Due", "Grand Total", "Balance Due"]
            },
            {
                "name": "line_items",
                "type": "array",
                "description": "Individual items or services billed",
                "required": False,
                "confidence_threshold": 0.7,
                "extraction_hints": ["Items", "Description", "Services"],
                "array_items": [
                    {
                        "name": "description",
                        "type": "text",
                        "description": "Item or service description",
                        "required": True,
                        "confidence_threshold": 0.75,
                        "extraction_hints": ["Description", "Item", "Service"]
                    },
                    {
                        "name": "quantity",
                        "type": "number",
                        "description": "Quantity of items",
                        "required": False,
                        "confidence_threshold": 0.7,
                        "extraction_hints": ["Qty", "Quantity", "Amount", "Count"]
                    },
                    {
                        "name": "unit_price",
                        "type": "number",
                        "description": "Price per unit",
                        "required": False,
                        "confidence_threshold": 0.7,
                        "extraction_hints": ["Price", "Rate", "Unit Price", "Cost"]
                    },
                    {
                        "name": "total",
                        "type": "number",
                        "description": "Line item total",
                        "required": False,
                        "confidence_threshold": 0.75,
                        "extraction_hints": ["Total", "Amount", "Line Total"]
                    }
                ]
            }
        ]
    },
    {
        "name": "Receipt",
        "category": "receipt",
        "description": "Purchase receipt with items and payment details",
        "icon": "🧾",
        "fields": [
            {
                "name": "receipt_number",
                "type": "text",
                "description": "Receipt or transaction ID",
                "required": False,
                "confidence_threshold": 0.75,
                "extraction_hints": ["Receipt #", "Transaction", "Order #", "Receipt No"]
            },
            {
                "name": "date",
                "type": "date",
                "description": "Purchase date",
                "required": True,
                "confidence_threshold": 0.8,
                "extraction_hints": ["Date", "Transaction Date", "Purchase Date"]
            },
            {
                "name": "merchant_name",
                "type": "text",
                "description": "Store or merchant name",
                "required": True,
                "confidence_threshold": 0.8,
                "extraction_hints": ["Store", "Merchant", "Retailer", "Sold By"]
            },
            {
                "name": "total",
                "type": "number",
                "description": "Total amount paid",
                "required": True,
                "confidence_threshold": 0.85,
                "extraction_hints": ["Total", "Amount", "Total Paid", "Grand Total"]
            },
            {
                "name": "payment_method",
                "type": "text",
                "description": "Payment type (cash, card, etc.)",
                "required": False,
                "confidence_threshold": 0.7,
                "extraction_hints": ["Payment", "Paid By", "Method", "Card", "Cash"]
            },
            {
                "name": "items",
                "type": "array",
                "description": "Purchased items",
                "required": False,
                "confidence_threshold": 0.7,
                "extraction_hints": ["Items", "Products"],
                "array_items": [
                    {
                        "name": "name",
                        "type": "text",
                        "description": "Item name",
                        "required": True,
                        "confidence_threshold": 0.75,
                        "extraction_hints": ["Item", "Product", "Description"]
                    },
                    {
                        "name": "price",
                        "type": "number",
                        "description": "Item price",
                        "required": True,
                        "confidence_threshold": 0.75,
                        "extraction_hints": ["Price", "Amount", "Cost"]
                    }
                ]
            }
        ]
    },
    {
        "name": "Contract",
        "category": "contract",
        "description": "Legal contract or agreement with parties and terms",
        "icon": "📜",
        "fields": [
            {
                "name": "contract_title",
                "type": "text",
                "description": "Contract or agreement name",
                "required": True,
                "confidence_threshold": 0.8,
                "extraction_hints": ["Agreement", "Contract", "Title"]
            },
            {
                "name": "effective_date",
                "type": "date",
                "description": "Date contract becomes effective",
                "required": True,
                "confidence_threshold": 0.8,
                "extraction_hints": ["Effective Date", "Start Date", "Dated", "Executed On"]
            },
            {
                "name": "expiration_date",
                "type": "date",
                "description": "Contract end or renewal date",
                "required": False,
                "confidence_threshold": 0.75,
                "extraction_hints": ["Expiration", "End Date", "Term", "Renewal Date"]
            },
            {
                "name": "party_a",
                "type": "text",
                "description": "First contracting party",
                "required": True,
                "confidence_threshold": 0.8,
                "extraction_hints": ["Party A", "First Party", "Provider", "Vendor"]
            },
            {
                "name": "party_b",
                "type": "text",
                "description": "Second contracting party",
                "required": True,
                "confidence_threshold": 0.8,
                "extraction_hints": ["Party B", "Second Party", "Client", "Customer"]
            },
            {
                "name": "contract_value",
                "type": "number",
                "description": "Total contract value",
                "required": False,
                "confidence_threshold": 0.75,
                "extraction_hints": ["Value", "Amount", "Total", "Contract Price"]
            },
            {
                "name": "payment_terms",
                "type": "text",
                "description": "Payment schedule and terms",
                "required": False,
                "confidence_threshold": 0.7,
                "extraction_hints": ["Payment Terms", "Payment Schedule", "Net", "Due"]
            },
            {
                "name": "termination_clause",
                "type": "text",
                "description": "Termination conditions",
                "required": False,
                "confidence_threshold": 0.65,
                "extraction_hints": ["Termination", "Cancellation", "Notice Period"]
            }
        ]
    },
    {
        "name": "Purchase Order",
        "category": "purchase_order",
        "description": "Purchase order for goods or services",
        "icon": "📦",
        "fields": [
            {
                "name": "po_number",
                "type": "text",
                "description": "Purchase order number",
                "required": True,
                "confidence_threshold": 0.85,
                "extraction_hints": ["PO #", "P.O. Number", "Purchase Order", "Order Number"]
            },
            {
                "name": "order_date",
                "type": "date",
                "description": "Date order was placed",
                "required": True,
                "confidence_threshold": 0.8,
                "extraction_hints": ["Order Date", "Date", "Issued", "PO Date"]
            },
            {
                "name": "delivery_date",
                "type": "date",
                "description": "Expected delivery date",
                "required": False,
                "confidence_threshold": 0.75,
                "extraction_hints": ["Delivery Date", "Ship Date", "Expected", "Due Date"]
            },
            {
                "name": "vendor_name",
                "type": "text",
                "description": "Supplier or vendor name",
                "required": True,
                "confidence_threshold": 0.8,
                "extraction_hints": ["Vendor", "Supplier", "Ship To", "Deliver To"]
            },
            {
                "name": "buyer_name",
                "type": "text",
                "description": "Purchasing company or person",
                "required": True,
                "confidence_threshold": 0.8,
                "extraction_hints": ["Buyer", "Purchaser", "Bill To", "Company"]
            },
            {
                "name": "total_amount",
                "type": "number",
                "description": "Total order amount",
                "required": True,
                "confidence_threshold": 0.85,
                "extraction_hints": ["Total", "Amount", "Grand Total", "Order Total"]
            },
            {
                "name": "shipping_address",
                "type": "text",
                "description": "Delivery address",
                "required": False,
                "confidence_threshold": 0.7,
                "extraction_hints": ["Ship To", "Delivery Address", "Shipping Address"]
            },
            {
                "name": "items",
                "type": "array",
                "description": "Ordered items",
                "required": False,
                "confidence_threshold": 0.7,
                "extraction_hints": ["Items", "Line Items", "Products"],
                "array_items": [
                    {
                        "name": "item_code",
                        "type": "text",
                        "description": "Product or item code",
                        "required": False,
                        "confidence_threshold": 0.7,
                        "extraction_hints": ["Code", "SKU", "Item #", "Product Code"]
                    },
                    {
                        "name": "description",
                        "type": "text",
                        "description": "Item description",
                        "required": True,
                        "confidence_threshold": 0.75,
                        "extraction_hints": ["Description", "Item", "Product"]
                    },
                    {
                        "name": "quantity",
                        "type": "number",
                        "description": "Quantity ordered",
                        "required": True,
                        "confidence_threshold": 0.75,
                        "extraction_hints": ["Qty", "Quantity", "Amount", "Count"]
                    },
                    {
                        "name": "unit_price",
                        "type": "number",
                        "description": "Price per unit",
                        "required": False,
                        "confidence_threshold": 0.75,
                        "extraction_hints": ["Price", "Unit Price", "Rate", "Cost"]
                    }
                ]
            }
        ]
    },
    {
        "name": "Generic Document",
        "category": "generic",
        "description": "Start from scratch with basic text extraction",
        "icon": "📄",
        "fields": [
            {
                "name": "document_title",
                "type": "text",
                "description": "Document title or subject",
                "required": False,
                "confidence_threshold": 0.75,
                "extraction_hints": ["Title", "Subject", "Re:"]
            },
            {
                "name": "date",
                "type": "date",
                "description": "Document date",
                "required": False,
                "confidence_threshold": 0.75,
                "extraction_hints": ["Date", "Dated"]
            },
            {
                "name": "content",
                "type": "text",
                "description": "Main document content",
                "required": False,
                "confidence_threshold": 0.7,
                "extraction_hints": []
            }
        ]
    }
]
