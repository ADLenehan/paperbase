"""
Query Expansion Service - Phase 2 Enhancement

Provides:
1. Synonym-based query expansion
2. Domain-specific term expansion
3. LLM-powered query rewriting (optional)
"""
import logging
import re
from typing import List, Optional

logger = logging.getLogger(__name__)


class QueryExpansionService:
    """
    Query expansion service for improving search recall.

    Uses domain-specific synonyms and related terms to expand queries
    for better matching without relying on LLM per query.
    """

    # Domain-specific synonym dictionary for document extraction
    SYNONYMS = {
        # Financial/Accounting
        "invoice": ["bill", "receipt", "statement", "charge"],
        "vendor": ["supplier", "provider", "seller", "merchant"],
        "customer": ["client", "buyer", "purchaser", "account"],
        "total": ["amount", "sum", "cost", "price", "value"],
        "payment": ["pay", "paid", "remittance", "settlement"],
        "tax": ["taxes", "taxation", "levy", "duty"],
        "fee": ["charge", "cost", "rate", "expense"],

        # Document types
        "contract": ["agreement", "deal", "arrangement"],
        "order": ["purchase", "po", "request"],
        "quote": ["quotation", "estimate", "proposal"],

        # Business entities
        "company": ["business", "corporation", "firm", "organization", "enterprise"],
        "address": ["location", "place", "site"],

        # Dates/Time
        "date": ["when", "time", "period"],
        "due": ["deadline", "expiry", "expiration"],

        # Actions
        "send": ["mail", "ship", "deliver", "transmit"],
        "receive": ["get", "obtain", "acquire"],

        # Crypto-specific (based on your documents)
        "crypto": ["cryptocurrency", "bitcoin", "digital asset", "token"],
        "wallet": ["address", "account", "cold storage"],
        "transaction": ["trade", "transfer", "exchange", "swap"],
        "reconciliation": ["matching", "verification", "audit"],
        "cpa": ["accountant", "tax professional", "tax preparer"],
        "tax preparation": ["tax filing", "tax return", "tax service"],
        "irs": ["internal revenue service", "tax authority"],
    }

    # Common stopwords to ignore (don't expand these)
    STOPWORDS = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "as", "is", "was", "are", "were",
        "be", "been", "being", "have", "has", "had", "do", "does", "did",
        "will", "would", "should", "could", "may", "might", "can",
        "this", "that", "these", "those", "what", "which", "who", "when", "where", "why", "how"
    }

    def __init__(self):
        # Precompute reverse index for faster lookups
        self._reverse_index = {}
        for term, synonyms in self.SYNONYMS.items():
            for syn in synonyms:
                if syn not in self._reverse_index:
                    self._reverse_index[syn] = []
                self._reverse_index[syn].append(term)

    def expand_query(self, query: str, max_expansions: int = 3) -> str:
        """
        Expand query with synonyms using PostgreSQL tsquery syntax.

        Args:
            query: Original search query (e.g., "invoice total")
            max_expansions: Maximum synonyms to add per term

        Returns:
            Expanded query in tsquery format
            Example: "invoice total" -> "(invoice | bill | receipt) & (total | amount | sum)"
        """
        # Clean and tokenize
        words = self._tokenize(query)

        expanded_terms = []
        for word in words:
            # Skip stopwords
            if word in self.STOPWORDS:
                continue

            # Find synonyms
            synonyms = self._find_synonyms(word, max_expansions)

            if synonyms:
                # Create OR group: (word | syn1 | syn2)
                terms = [word] + synonyms
                expanded_terms.append(f"({' | '.join(terms)})")
            else:
                # No synonyms, use word as-is
                expanded_terms.append(word)

        # Join with AND
        if not expanded_terms:
            return query  # Fallback to original

        expanded_query = ' & '.join(expanded_terms)
        logger.info(f"Query expansion: '{query}' -> '{expanded_query}'")

        return expanded_query

    def expand_simple(self, query: str) -> str:
        """
        Simple expansion that preserves natural language for plainto_tsquery.

        Args:
            query: "invoice total"

        Returns:
            "invoice bill receipt total amount sum"
        """
        words = self._tokenize(query)
        all_terms = set(words)

        for word in words:
            if word not in self.STOPWORDS:
                synonyms = self._find_synonyms(word, max_expansions=2)
                all_terms.update(synonyms)

        expanded = ' '.join(all_terms)
        logger.info(f"Simple expansion: '{query}' -> '{expanded}'")

        return expanded

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text into words."""
        # Lowercase and extract words
        text = text.lower()
        words = re.findall(r'\b\w+\b', text)
        return words

    def _find_synonyms(self, word: str, max_count: int = 3) -> List[str]:
        """
        Find synonyms for a word.

        Args:
            word: Word to find synonyms for
            max_count: Maximum synonyms to return

        Returns:
            List of synonyms (up to max_count)
        """
        synonyms = []

        # Direct lookup
        if word in self.SYNONYMS:
            synonyms = self.SYNONYMS[word][:max_count]

        # Reverse lookup (word might be a synonym of another term)
        elif word in self._reverse_index:
            # Get the main terms that have this word as synonym
            main_terms = self._reverse_index[word]
            for main_term in main_terms:
                # Add the main term and its other synonyms
                synonyms.append(main_term)
                synonyms.extend([s for s in self.SYNONYMS[main_term] if s != word])

                if len(synonyms) >= max_count:
                    break

        return synonyms[:max_count]

    def suggest_corrections(self, query: str, available_terms: List[str], threshold: float = 0.6) -> Optional[str]:
        """
        Suggest spelling corrections based on available terms.

        This is a placeholder - actual implementation would use pg_trgm similarity.

        Args:
            query: User's query
            available_terms: List of known terms from index
            threshold: Similarity threshold (0-1)

        Returns:
            Corrected query or None
        """
        # This would be implemented with pg_trgm in PostgreSQL
        # For now, return None (no correction)
        return None

    async def expand_with_llm(
        self,
        query: str,
        claude_service,
        num_variations: int = 3
    ) -> List[str]:
        """
        Use Claude to generate semantic variations of the query.

        This is more expensive but higher quality than synonym expansion.

        Args:
            query: Original query
            claude_service: ClaudeService instance
            num_variations: Number of variations to generate

        Returns:
            List of alternative queries including original
        """
        try:
            prompt = f'''Generate {num_variations} alternative phrasings of this search query.
Each alternative should have the same intent but use different words.

Original query: "{query}"

Return ONLY a JSON array of alternative queries (including the original):
["original query", "alternative 1", "alternative 2"]

Keep queries concise (under 15 words each).'''

            # This would call claude_service.generate_text()
            # For now, placeholder
            logger.info(f"LLM expansion requested for: '{query}' (not implemented)")

            return [query]  # Return original only for now

        except Exception as e:
            logger.error(f"LLM expansion failed: {e}")
            return [query]  # Fallback to original


# Module-level singleton
_query_expander = None


def get_query_expander() -> QueryExpansionService:
    """Get singleton instance of QueryExpansionService."""
    global _query_expander
    if _query_expander is None:
        _query_expander = QueryExpansionService()
    return _query_expander
