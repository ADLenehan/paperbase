# Natural Language Query Interface - User Guide

## 🎯 Overview

The Natural Language Query interface allows you to search and analyze your documents using plain English questions. No need to learn complex query syntax or filters - just ask naturally!

## 🚀 Getting Started

### Accessing the Interface

1. Navigate to the **"Ask AI"** tab in the main navigation
2. You'll see a chat-like interface with example questions on the right sidebar
3. Type your question in the input box at the bottom and press Enter or click "Ask"

### Example Questions

#### Basic Search Queries
- "Show me all invoices from Acme Corp"
- "Find contracts uploaded last week"
- "Documents with low confidence scores"
- "Show me receipts over $100"

#### Date-Based Queries
- "Invoices from last month"
- "Contracts expiring in 30 days"
- "All documents from Q4 2024"
- "Year-to-date invoices"
- "Documents uploaded this week"

#### Analytics & Aggregations
- "What's the total value of all invoices?"
- "Average invoice amount by vendor"
- "Total spending this year"
- "How many documents were processed last month?"
- "Top 5 vendors by invoice count"

#### Anomaly Detection
- "Find duplicate invoices"
- "Show unusually high invoice amounts"
- "Documents with low confidence extractions"
- "Find invoices that might need review"

#### Comparisons
- "Compare spending: last month vs this month"
- "Show monthly upload trends"
- "Vendor spending comparison"

## 💡 Tips for Better Results

### 1. Be Specific with Amounts
❌ "Show me expensive invoices"
✅ "Show me invoices over $5,000"

### 2. Use Relative Dates
- "last month" - Previous complete calendar month
- "last quarter" - Previous complete quarter (Q1, Q2, Q3, Q4)
- "this year" or "YTD" - January 1st to today
- "last 30 days" - Rolling 30-day window
- "Q4 2024" - Oct 1 - Dec 31, 2024
- "in 30 days" - Today through 30 days from now

### 3. Leverage Fuzzy Matching
The system understands variations:
- "Acme" matches "Acme Corp", "ACME Inc", "Acme Corporation"
- "inv" matches "invoice"
- Common typos are handled gracefully

### 4. Ask for Aggregations
- "total" → sums values
- "average" → calculates mean
- "by vendor" → groups results
- "count" → counts documents

### 5. Follow Up Questions
The system remembers your conversation:
- First: "Show me invoices from Acme"
- Follow-up: "What's the total?"
- Follow-up: "Show me last month's instead"

## 📊 Understanding Results

### Result Display

Each query result shows:

1. **Summary**: Conversational explanation of what was found
2. **Query Explanation**: Technical details of what was searched
3. **Results Preview**: Top matching documents with key fields
4. **Aggregations**: Charts/stats for analytical queries
5. **Suggested Actions**: Context-aware next steps

### Result Components

#### For Search Queries
```
Found 23 invoices from Acme Corp totaling $47,200.
The largest invoice was $8,500, and 3 are currently past due.

📄 Results (showing 5 of 23):
- invoice_001.pdf - $8,500 - Oct 15, 2024
- invoice_002.pdf - $3,200 - Oct 20, 2024
...

💡 Suggested Actions:
- Export results to CSV
- Flag items for review
```

#### For Aggregation Queries
```
You've received 145 invoices this quarter, averaging $2,340 each.
Your top vendor is Acme Corp with $31,000 in invoices.

[Bar Chart showing spending by vendor]

💡 Suggested Actions:
- View detailed breakdown
- Download report
```

## 🎨 Interface Features

### Chat History
- All queries and responses are preserved in the current session
- Scroll up to review previous results
- Reference earlier answers in follow-up questions

### Suggested Questions Sidebar
- **Search & Filter**: Basic document finding
- **Analytics & Aggregation**: Calculate totals, averages, counts
- **Quality & Anomalies**: Find issues or patterns
- **Trends & Insights**: Discover patterns over time

Click any suggested question to run it immediately.

### Smart Clarifications
If your query is ambiguous, the AI will ask for clarification:
```
User: "Show me the expensive ones"
AI: "I'd be happy to help! Could you clarify:
     1. What document type? (invoices, contracts, receipts)
     2. What price threshold defines 'expensive'?"
```

## ⚙️ Advanced Features

### Date Parsing Intelligence

The system understands context:
- **Current date**: Always considers "today" when parsing relative dates
- **Quarter calculation**: Q1=Jan-Mar, Q2=Apr-Jun, Q3=Jul-Sep, Q4=Oct-Dec
- **Business context**: "last quarter" = previous complete quarter, not just 3 months ago

### Fuzzy Matching

Vendor name matching is intelligent:
```
Query: "invoices from acme"
Matches:
- Acme Corporation
- ACME Inc
- Acme Corp.
- The Acme Company
```

### Compound Queries

Combine multiple filters:
```
"Show me invoices from Acme Corp over $5,000 from last quarter"

Translates to:
- Field filter: vendor ~ "Acme"
- Range filter: amount > 5000
- Date filter: 2024-07-01 to 2024-09-30
```

### Anomaly Detection

Built-in patterns:
- **Duplicates**: Same vendor + amount + nearby dates
- **Outliers**: Amounts significantly above vendor average
- **Low confidence**: Extractions below quality threshold

## 🔧 Technical Details

### Supported Query Types

1. **Search**: Find specific documents with filters
2. **Aggregation**: Calculate sums, averages, counts, group-by
3. **Anomaly**: Find unusual patterns or duplicates
4. **Comparison**: Compare metrics across time periods

### Available Fields

The system searches across all extracted fields:
- Standard fields: filename, uploaded_at, processed_at, status
- Template fields: vendor, total, invoice_number, date, etc.
- Confidence scores: Per-field extraction quality

### Elasticsearch Integration

Behind the scenes, your natural language query is translated to Elasticsearch DSL:
- **Match queries**: For fuzzy text search
- **Range queries**: For dates and numbers
- **Term queries**: For exact matches
- **Bool queries**: For combining filters with AND/OR logic

## 📈 Use Cases

### 1. Financial Analysis
```
"What's my total spending by vendor this year?"
"Show me all invoices over $10,000"
"Which vendors have I paid the most?"
"Average invoice amount last quarter"
```

### 2. Document Management
```
"Find all contracts expiring in the next 60 days"
"Show me documents uploaded but not yet processed"
"Which documents have errors?"
```

### 3. Quality Control
```
"Find extractions with low confidence scores"
"Show me potential duplicate invoices"
"Which documents need verification?"
"Find unusually high invoice amounts"
```

### 4. Trend Analysis
```
"Compare spending: last month vs this month"
"Show monthly document upload trend"
"Top 5 vendors by transaction count"
"How has processing volume changed over time?"
```

## 🐛 Troubleshooting

### "No results found"
- Try broader search terms
- Check date ranges (maybe no documents in that period)
- Verify field names (ask "what fields are available?")

### "I don't understand that query"
- Be more specific with amounts and dates
- Break complex queries into simpler ones
- Try one of the suggested example questions

### Slow responses
- Complex aggregations on large datasets may take 5-10 seconds
- The AI needs to translate your query and search the database
- Results are worth the wait!

### Unexpected results
- Ask for clarification: "Why did you show these results?"
- Refine your query with more specific terms
- Use exact field names when possible

## 🚦 Best Practices

1. **Start simple**: Begin with basic queries, then add complexity
2. **Use examples**: Click suggested questions to see query patterns
3. **Follow up**: Ask clarifying questions in the same conversation
4. **Be specific**: Include amounts, dates, vendor names when relevant
5. **Check explanations**: Read the "What I searched for" section
6. **Review suggestions**: Act on suggested next steps

## 🔮 Coming Soon

- Export results to CSV/Excel
- Save favorite queries
- Schedule automated reports
- Email alerts for specific conditions
- Custom visualizations
- Multi-language support

## 📞 Support

If you encounter issues or have questions:
- Check the example queries in the sidebar
- Review this guide for tips
- Report bugs via GitHub Issues
- Request features via the feedback form

---

**Version**: 1.0
**Last Updated**: 2025-10-12
**Powered by**: Claude 3.5 Sonnet + Elasticsearch
