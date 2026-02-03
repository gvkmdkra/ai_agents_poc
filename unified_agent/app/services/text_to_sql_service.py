"""
Text-to-SQL Service
Converts natural language queries to SQL and executes them
"""

import re
import time
from typing import Dict, Any, Optional, List, Tuple
from openai import OpenAI

from app.core.config import settings
from app.core.logging import get_logger
from app.core.exceptions import TextToSQLError, DatabaseError
from .vector_store import VectorStore
from .mysql_service import MySQLService

logger = get_logger(__name__)


class TextToSQLService:
    """
    Text-to-SQL service for converting natural language to SQL queries
    Supports user data isolation and fast mode for voice calls
    """

    # Pre-defined query patterns for fast matching
    QUERY_PATTERNS = {
        r"how many (?:active )?clients?": "SELECT COUNT(*) as count FROM clients WHERE status = 'active'",
        r"how many users?": "SELECT COUNT(*) as count FROM users",
        r"how many projects?": "SELECT COUNT(*) as count FROM projects",
        r"how many invoices?": "SELECT COUNT(*) as count FROM invoices",
        r"list (?:all )?clients?": "SELECT id, name, email, status FROM clients LIMIT 10",
        r"list (?:all )?users?": "SELECT id, name, email FROM users LIMIT 10",
        r"total revenue": "SELECT SUM(amount) as total_revenue FROM invoices WHERE status = 'paid'",
    }

    def __init__(
        self,
        tenant_id: str,
        index_name: Optional[str] = None,
        userid: Optional[int] = None
    ):
        """
        Initialize Text-to-SQL service

        Args:
            tenant_id: Tenant identifier
            index_name: Pinecone index for view metadata
            userid: User ID for data filtering
        """
        self.tenant_id = tenant_id
        self.userid = userid
        self.client_id = None

        # Initialize services
        self._openai = OpenAI(api_key=settings.openai_api_key)
        self._vector_store = VectorStore(index_name=index_name) if index_name else None
        self._mysql_service = MySQLService()

        # Lookup client_id for data filtering
        if userid:
            self._lookup_client_id()

    def _lookup_client_id(self) -> None:
        """Lookup client_id from userid for data filtering"""
        try:
            result = self._mysql_service.execute_query(
                f"SELECT client_id FROM applicant WHERE id = {self.userid} LIMIT 1"
            )
            if result and len(result) > 0:
                self.client_id = result[0].get("client_id")
                logger.info(f"Resolved userid {self.userid} to client_id {self.client_id}")
        except Exception as e:
            logger.warning(f"Failed to lookup client_id: {e}")

    def classify_query(self, query: str) -> str:
        """
        Classify query type using LLM

        Args:
            query: User's natural language query

        Returns:
            Query type: DATABASE_QUERY, RAG, CONVERSATIONAL, or OFF_TOPIC
        """
        try:
            classification_prompt = f"""Classify this user question into one of these categories:

User question: "{query}"

Categories:
- DATABASE_QUERY: Questions about specific data, counts, statistics, client info, user details, business metrics
- RAG: Questions about documentation, policies, procedures, general knowledge
- CONVERSATIONAL: Greetings, thanks, general conversation
- OFF_TOPIC: Questions completely unrelated to business

Return ONLY one word: DATABASE_QUERY, RAG, CONVERSATIONAL, or OFF_TOPIC"""

            response = self._openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": classification_prompt}],
                temperature=0,
                max_tokens=20
            )

            classification = response.choices[0].message.content.strip().upper()

            if classification not in ["DATABASE_QUERY", "RAG", "CONVERSATIONAL", "OFF_TOPIC"]:
                return "CONVERSATIONAL"

            return classification

        except Exception as e:
            logger.error(f"Query classification failed: {e}")
            return "CONVERSATIONAL"

    def _match_pattern(self, query: str) -> Optional[str]:
        """
        Match query against pre-defined patterns for fast response

        Args:
            query: User's query

        Returns:
            SQL query if pattern matches, None otherwise
        """
        query_lower = query.lower().strip()

        for pattern, sql in self.QUERY_PATTERNS.items():
            if re.search(pattern, query_lower):
                logger.debug(f"Pattern matched: {pattern}")
                return sql

        return None

    def select_relevant_views(self, query: str) -> List[Dict[str, Any]]:
        """
        Select relevant database views for the query

        Args:
            query: User's query

        Returns:
            List of relevant views with columns
        """
        if not self._vector_store:
            logger.warning("Vector store not configured for view selection")
            return []

        return self._vector_store.search_relevant_views(
            query=query,
            tenant_id=self.tenant_id,
            top_k=3
        )

    def generate_sql(
        self,
        query: str,
        views: List[Dict[str, Any]]
    ) -> Optional[str]:
        """
        Generate SQL from natural language query

        Args:
            query: User's query
            views: Available views and their columns

        Returns:
            Generated SQL query
        """
        try:
            # Build schema context
            schema_context = ""
            for view in views:
                columns = ", ".join([
                    f"{col['column_name']} ({col.get('data_type', 'unknown')})"
                    for col in view.get("columns", [])
                ])
                schema_context += f"- {view['view_name']}: {columns}\n"

            # Add client_id filter instruction if applicable
            filter_instruction = ""
            if self.client_id:
                filter_instruction = f"""
IMPORTANT: For data security, you MUST filter all queries by client_id = {self.client_id}
If the table has a client_id column, add WHERE client_id = {self.client_id} or AND client_id = {self.client_id}
"""

            prompt = f"""Generate a SQL query for this question.

Question: {query}

Available views and columns:
{schema_context}

{filter_instruction}

Rules:
1. ONLY use SELECT statements
2. ALWAYS add LIMIT 100 unless counting
3. Use column names EXACTLY as shown above
4. Return ONLY the SQL query, no explanations
5. If you cannot answer with available views, return: SELECT 'Cannot answer with available data' as error"""

            response = self._openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=500
            )

            sql = response.choices[0].message.content.strip()

            # Clean up SQL
            sql = sql.replace("```sql", "").replace("```", "").strip()

            # Security check
            if not self._is_safe_sql(sql):
                raise TextToSQLError("Generated SQL failed security validation")

            return sql

        except Exception as e:
            logger.error(f"SQL generation failed: {e}")
            raise TextToSQLError(f"Failed to generate SQL: {e}")

    def _is_safe_sql(self, sql: str) -> bool:
        """
        Validate SQL for security

        Args:
            sql: SQL query to validate

        Returns:
            True if safe
        """
        sql_upper = sql.upper().strip()

        # Must be SELECT only
        if not sql_upper.startswith("SELECT"):
            logger.warning(f"Non-SELECT query rejected: {sql[:50]}")
            return False

        # Check for dangerous keywords
        dangerous = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "EXECUTE", "EXEC"]
        for keyword in dangerous:
            if keyword in sql_upper:
                logger.warning(f"Dangerous keyword '{keyword}' found in query")
                return False

        return True

    def format_response(
        self,
        query: str,
        sql: str,
        results: List[Dict[str, Any]]
    ) -> str:
        """
        Format SQL results as natural language

        Args:
            query: Original query
            sql: Executed SQL
            results: Query results

        Returns:
            Natural language response
        """
        try:
            if not results:
                return "I couldn't find any data matching your query."

            # For simple counts
            if len(results) == 1 and "count" in results[0]:
                count = results[0]["count"]
                return f"The count is {count}."

            # For list results (simple formatting for voice)
            if len(results) <= 5:
                items = []
                for row in results:
                    # Get the most relevant fields
                    name = row.get("name", row.get("title", row.get("id", "Item")))
                    items.append(str(name))

                if len(items) == 1:
                    return f"I found: {items[0]}"
                return f"I found {len(items)} items: {', '.join(items)}"

            # For larger results, use LLM
            prompt = f"""Convert these SQL results to a natural, conversational response.

Original question: {query}
Results: {results[:10]}  # First 10 rows
Total rows: {len(results)}

Keep the response concise and suitable for voice (under 100 words)."""

            response = self._openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=200
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.error(f"Response formatting failed: {e}")
            return f"I found {len(results)} results for your query."

    def _format_response_simple(
        self,
        results: List[Dict[str, Any]]
    ) -> str:
        """
        Simple response formatting without LLM (fast mode)

        Args:
            results: Query results

        Returns:
            Formatted response
        """
        if not results:
            return "No data found."

        # Handle count queries
        if len(results) == 1:
            row = results[0]
            if "count" in row or "COUNT(*)" in row:
                count = row.get("count", row.get("COUNT(*)"))
                return f"The total count is {count}."

            if "total" in str(row).lower():
                for key, value in row.items():
                    if "total" in key.lower() or "sum" in key.lower():
                        return f"The total is {value}."

        # Handle list queries
        if len(results) <= 10:
            items = []
            for row in results:
                name = row.get("name", row.get("title", row.get("email", list(row.values())[0])))
                items.append(str(name))

            if len(items) == 1:
                return f"I found: {items[0]}"

            return f"I found {len(items)} items: {', '.join(items[:5])}" + (
                f" and {len(items) - 5} more" if len(items) > 5 else ""
            )

        return f"I found {len(results)} results."

    def process_query(self, query: str) -> Dict[str, Any]:
        """
        Process a natural language query (full pipeline)

        Args:
            query: User's query

        Returns:
            Response with results and metadata
        """
        start_time = time.time()

        try:
            # Classify query
            query_type = self.classify_query(query)

            if query_type != "DATABASE_QUERY":
                return {
                    "success": False,
                    "query_type": query_type,
                    "message": "This query doesn't require database access."
                }

            # Select relevant views
            views = self.select_relevant_views(query)

            if not views:
                return {
                    "success": False,
                    "error": "No relevant database views found for this query."
                }

            # Generate SQL
            sql = self.generate_sql(query, views)

            # Execute query
            results = self._mysql_service.execute_query(sql)

            # Format response
            formatted_response = self.format_response(query, sql, results)

            processing_time = int((time.time() - start_time) * 1000)

            return {
                "success": True,
                "formatted_response": formatted_response,
                "sql": sql,
                "result": results,
                "row_count": len(results),
                "processing_time_ms": processing_time
            }

        except Exception as e:
            logger.error(f"Query processing failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def process_query_fast(self, query: str) -> Dict[str, Any]:
        """
        Process query in fast mode (optimized for voice, <4 seconds target)

        Args:
            query: User's query

        Returns:
            Response with results and metadata
        """
        start_time = time.time()

        try:
            # Try pattern matching first (instant)
            pattern_sql = self._match_pattern(query)

            if pattern_sql:
                # Add client_id filter if applicable
                if self.client_id and "WHERE" in pattern_sql.upper():
                    pattern_sql = pattern_sql.replace(
                        "WHERE",
                        f"WHERE client_id = {self.client_id} AND"
                    )
                elif self.client_id:
                    pattern_sql = pattern_sql.replace(
                        "LIMIT",
                        f"WHERE client_id = {self.client_id} LIMIT"
                    )

                results = self._mysql_service.execute_query(pattern_sql)
                formatted = self._format_response_simple(results)

                return {
                    "success": True,
                    "formatted_response": formatted,
                    "sql": pattern_sql,
                    "result": results,
                    "row_count": len(results),
                    "processing_time_ms": int((time.time() - start_time) * 1000),
                    "mode": "pattern_match"
                }

            # Fallback to full pipeline (but with simple formatting)
            views = self.select_relevant_views(query)

            if not views:
                return {
                    "success": False,
                    "formatted_response": "I couldn't find relevant data for your query.",
                    "error": "No views found"
                }

            sql = self.generate_sql(query, views)
            results = self._mysql_service.execute_query(sql)
            formatted = self._format_response_simple(results)

            return {
                "success": True,
                "formatted_response": formatted,
                "sql": sql,
                "result": results,
                "row_count": len(results),
                "processing_time_ms": int((time.time() - start_time) * 1000),
                "mode": "generated"
            }

        except Exception as e:
            logger.error(f"Fast query processing failed: {e}")
            return {
                "success": False,
                "formatted_response": "I encountered an error processing your query.",
                "error": str(e)
            }
