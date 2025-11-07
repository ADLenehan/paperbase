# Quick Test Guide - Natural Language Query Interface

## 🚀 Quick Start

### 1. Start the Backend
```bash
cd backend
source venv/bin/activate  # or your virtual environment
uvicorn app.main:app --reload
```

Backend should be running at: http://localhost:8000

### 2. Start the Frontend
```bash
cd frontend
npm run dev
```

Frontend should be running at: http://localhost:5173

### 3. Access the Interface
- Open browser to http://localhost:5173
- Click **"Ask AI"** in the navigation bar
- You should see a chat interface with example questions on the right

## 🧪 Test Queries

### Basic Functionality Tests

**Test 1: Simple Search**
```
Query: "Show me all invoices"
Expected: List of all invoice documents with summary
```

**Test 2: Vendor Filter**
```
Query: "Find documents from Acme Corp"
Expected: Documents with vendor containing "Acme"
```

**Test 3: Amount Filter**
```
Query: "Show me invoices over $1000"
Expected: Documents with amount > 1000
```

### Date Parsing Tests

**Test 4: Last Month**
```
Query: "Documents from last month"
Expected: Documents from previous calendar month (Sep 1-30 if today is Oct 12)
```

**Test 5: This Year**
```
Query: "All documents this year"
Expected: Documents from Jan 1 to today
```

**Test 6: Quarter Notation**
```
Query: "Invoices from Q3 2024"
Expected: Documents from July 1 - Sep 30, 2024
```

### Aggregation Tests

**Test 7: Sum Aggregation**
```
Query: "What's the total value of all invoices?"
Expected: Sum displayed in blue card, list of matching invoices
```

**Test 8: Average**
```
Query: "Average invoice amount this year"
Expected: Average displayed in green card with count
```

**Test 9: Group By**
```
Query: "Total spending by vendor"
Expected: Breakdown showing vendor names with totals and counts
```

### Compound Query Tests

**Test 10: Multiple Filters**
```
Query: "Invoices from Acme Corp over $5000 from last quarter"
Expected: Documents matching all three conditions
```

### Error Handling Tests

**Test 11: No Results**
```
Query: "Documents from year 2050"
Expected: Friendly "no results" message with suggestions
```

**Test 12: Ambiguous Query**
```
Query: "Show me the expensive ones"
Expected: Clarifying question asking for document type and amount threshold
```

## 🔍 What to Look For

### Backend Logs
Watch for these in the terminal:
```
INFO - Parsed NL query: type=search, needs_clarification=False
INFO - Searching with query: ...
INFO - Generated summary for X results
```

### Frontend Display
Check that you see:
- ✅ User message appears on the right (blue background)
- ✅ AI response appears on the left (white card)
- ✅ Loading animation shows while processing
- ✅ Results preview displays (top 5 documents)
- ✅ Suggested actions appear as buttons
- ✅ Aggregations display correctly (totals, averages, breakdowns)
- ✅ Timestamps show for all messages
- ✅ Sidebar suggestions are clickable

## 🐛 Common Issues

### Backend won't start
```bash
# Make sure dependencies are installed
pip install anthropic elasticsearch fastapi uvicorn sqlalchemy

# Check that .env file has required keys
cat .env | grep -E "(ANTHROPIC_API_KEY|ELASTICSEARCH_URL)"
```

### Frontend won't start
```bash
# Install dependencies
npm install

# Check that vite.config.js exists
ls vite.config.js
```

### API errors in console
Check:
1. Backend is running on port 8000
2. Frontend `VITE_API_URL` points to correct backend
3. CORS is enabled in backend (should be by default)

### No results when you have documents
Check:
1. Documents are indexed in Elasticsearch
2. Field names match what you're querying
3. Date ranges are correct (check current date context)

### Claude API errors
Check:
1. `ANTHROPIC_API_KEY` is set in `.env`
2. Key is valid and has credits
3. Network can reach Anthropic API

## ✅ Success Criteria

You should be able to:
- [x] Ask a question and get a response
- [x] See results displayed in a chat format
- [x] Click suggested questions and have them execute
- [x] View aggregations (totals, averages, etc.)
- [x] Get conversational summaries of results
- [x] See suggested next actions
- [x] Ask follow-up questions
- [x] Handle errors gracefully

## 📸 Screenshot Checklist

Take screenshots of:
1. Main interface with example questions sidebar
2. A simple search query result
3. An aggregation query with chart/stats
4. The suggested actions buttons
5. Error handling (no results case)

## 🎉 Next Steps

Once basic tests pass:

1. **Test with Real Data**: Upload some documents and try realistic queries
2. **Test Edge Cases**: Very long queries, special characters, multiple languages
3. **Performance**: Time how long queries take (should be < 5 seconds)
4. **Mobile**: Check if interface is responsive
5. **Conversation**: Try 3-4 follow-up questions in sequence

## 📝 Bug Report Template

If you find issues, report with:
```
**Query**: "exact query text"
**Expected**: what should happen
**Actual**: what actually happened
**Logs**: relevant backend logs
**Screenshot**: (attach if UI issue)
**Browser**: Chrome/Firefox/Safari version
```

---

**Happy Testing! 🚀**

If everything works, you now have a powerful natural language interface for document search and analytics!
