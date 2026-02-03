"""
Vector Store Service
Manages Pinecone vector database for RAG and Text-to-SQL metadata
"""

from typing import List, Dict, Any, Optional
from pinecone import Pinecone
from openai import OpenAI

from app.core.config import settings
from app.core.logging import get_logger
from app.core.exceptions import ExternalServiceError

logger = get_logger(__name__)


class VectorStore:
    """
    Vector store service for document embeddings and similarity search
    Supports both RAG document retrieval and Text-to-SQL view metadata
    """

    def __init__(self, index_name: Optional[str] = None):
        """
        Initialize vector store

        Args:
            index_name: Pinecone index name (uses default from settings if not provided)
        """
        self.index_name = index_name or settings.pinecone_index_name

        if not settings.pinecone_api_key:
            raise ExternalServiceError("pinecone", "Pinecone API key not configured")

        # Initialize clients
        self._pc = Pinecone(api_key=settings.pinecone_api_key)
        self._openai = OpenAI(api_key=settings.openai_api_key)
        self._index = None

    @property
    def index(self):
        """Lazy load Pinecone index"""
        if self._index is None:
            if not self.index_name:
                raise ExternalServiceError("pinecone", "No index name specified")
            self._index = self._pc.Index(self.index_name)
        return self._index

    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for text using OpenAI

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        try:
            response = self._openai.embeddings.create(
                model=settings.openai_embedding_model,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            raise ExternalServiceError("openai", f"Failed to generate embedding: {e}")

    def similarity_search(
        self,
        query: str,
        k: int = None,
        filter_dict: Optional[Dict[str, Any]] = None,
        include_metadata: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Search for similar documents

        Args:
            query: Search query
            k: Number of results (defaults to settings.pinecone_top_k)
            filter_dict: Metadata filter
            include_metadata: Include document metadata

        Returns:
            List of matching documents with scores
        """
        k = k or settings.pinecone_top_k

        try:
            # Generate query embedding
            query_embedding = self.generate_embedding(query)

            # Search Pinecone
            results = self.index.query(
                vector=query_embedding,
                top_k=k,
                filter=filter_dict,
                include_metadata=include_metadata
            )

            # Format results
            documents = []
            for match in results.matches:
                doc = {
                    "id": match.id,
                    "score": match.score,
                    "content": match.metadata.get("content", "") if match.metadata else "",
                    "metadata": match.metadata or {}
                }
                documents.append(doc)

            logger.debug(f"Similarity search returned {len(documents)} results")
            return documents

        except Exception as e:
            logger.error(f"Similarity search failed: {e}")
            raise ExternalServiceError("pinecone", f"Search failed: {e}")

    def index_document(
        self,
        doc_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Index a document in the vector store

        Args:
            doc_id: Document ID
            content: Document content
            metadata: Additional metadata

        Returns:
            True if successful
        """
        try:
            # Generate embedding
            embedding = self.generate_embedding(content)

            # Prepare metadata
            doc_metadata = metadata or {}
            doc_metadata["content"] = content[:1000]  # Store truncated content

            # Upsert to Pinecone
            self.index.upsert(
                vectors=[(doc_id, embedding, doc_metadata)]
            )

            logger.debug(f"Indexed document: {doc_id}")
            return True

        except Exception as e:
            logger.error(f"Document indexing failed: {e}")
            raise ExternalServiceError("pinecone", f"Indexing failed: {e}")

    def delete_documents(
        self,
        ids: Optional[List[str]] = None,
        filter_dict: Optional[Dict[str, Any]] = None,
        delete_all: bool = False
    ) -> bool:
        """
        Delete documents from the vector store

        Args:
            ids: List of document IDs to delete
            filter_dict: Metadata filter for batch deletion
            delete_all: Delete all documents

        Returns:
            True if successful
        """
        try:
            if delete_all:
                self.index.delete(delete_all=True)
            elif ids:
                self.index.delete(ids=ids)
            elif filter_dict:
                self.index.delete(filter=filter_dict)
            else:
                logger.warning("No deletion criteria specified")
                return False

            logger.info("Documents deleted successfully")
            return True

        except Exception as e:
            logger.error(f"Document deletion failed: {e}")
            raise ExternalServiceError("pinecone", f"Deletion failed: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get index statistics

        Returns:
            Index statistics
        """
        try:
            stats = self.index.describe_index_stats()
            return {
                "total_vectors": stats.total_vector_count,
                "dimension": stats.dimension,
                "namespaces": dict(stats.namespaces) if stats.namespaces else {}
            }
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {}

    # ============================================
    # TEXT-TO-SQL SPECIFIC METHODS
    # ============================================

    def get_view_columns(
        self,
        view_name: str,
        tenant_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get column metadata for a database view

        Args:
            view_name: Name of the database view
            tenant_id: Optional tenant filter

        Returns:
            List of column metadata
        """
        try:
            # Build filter
            filter_dict = {"view_name": view_name}
            if tenant_id:
                filter_dict["tenant_id"] = tenant_id

            # Search for view metadata
            results = self.index.query(
                vector=[0.0] * 1536,  # Dummy vector for metadata-only search
                top_k=100,
                filter=filter_dict,
                include_metadata=True
            )

            # Extract column info
            columns = []
            for match in results.matches:
                if match.metadata:
                    columns.append({
                        "column_name": match.metadata.get("column_name"),
                        "data_type": match.metadata.get("data_type"),
                        "description": match.metadata.get("description", ""),
                        "sample_values": match.metadata.get("sample_values", [])
                    })

            return columns

        except Exception as e:
            logger.error(f"Failed to get view columns: {e}")
            return []

    def index_view_metadata(
        self,
        view_name: str,
        columns: List[Dict[str, Any]],
        tenant_id: str,
        description: Optional[str] = None
    ) -> bool:
        """
        Index database view metadata for Text-to-SQL

        Args:
            view_name: Name of the database view
            columns: List of column metadata
            tenant_id: Tenant ID
            description: View description

        Returns:
            True if successful
        """
        try:
            vectors = []

            for column in columns:
                # Create searchable text for the column
                column_text = f"View: {view_name}, Column: {column['column_name']}, Type: {column.get('data_type', 'unknown')}"
                if column.get("description"):
                    column_text += f", Description: {column['description']}"

                # Generate embedding
                embedding = self.generate_embedding(column_text)

                # Prepare metadata
                metadata = {
                    "view_name": view_name,
                    "column_name": column["column_name"],
                    "data_type": column.get("data_type", "unknown"),
                    "description": column.get("description", ""),
                    "sample_values": column.get("sample_values", [])[:5],
                    "tenant_id": tenant_id,
                    "type": "view_metadata"
                }

                doc_id = f"{tenant_id}_{view_name}_{column['column_name']}"
                vectors.append((doc_id, embedding, metadata))

            # Batch upsert
            if vectors:
                self.index.upsert(vectors=vectors)
                logger.info(f"Indexed {len(vectors)} columns for view: {view_name}")

            return True

        except Exception as e:
            logger.error(f"Failed to index view metadata: {e}")
            raise ExternalServiceError("pinecone", f"View metadata indexing failed: {e}")

    def search_relevant_views(
        self,
        query: str,
        tenant_id: str,
        top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Search for relevant database views based on query

        Args:
            query: User's natural language query
            tenant_id: Tenant ID
            top_k: Number of views to return

        Returns:
            List of relevant views with their columns
        """
        try:
            # Generate query embedding
            query_embedding = self.generate_embedding(query)

            # Search with tenant filter
            results = self.index.query(
                vector=query_embedding,
                top_k=top_k * 10,  # Get more results to group by view
                filter={
                    "tenant_id": tenant_id,
                    "type": "view_metadata"
                },
                include_metadata=True
            )

            # Group by view name
            views = {}
            for match in results.matches:
                if match.metadata:
                    view_name = match.metadata.get("view_name")
                    if view_name:
                        if view_name not in views:
                            views[view_name] = {
                                "view_name": view_name,
                                "columns": [],
                                "max_score": match.score
                            }
                        views[view_name]["columns"].append({
                            "column_name": match.metadata.get("column_name"),
                            "data_type": match.metadata.get("data_type"),
                            "description": match.metadata.get("description", "")
                        })

            # Sort by relevance and return top views
            sorted_views = sorted(
                views.values(),
                key=lambda x: x["max_score"],
                reverse=True
            )[:top_k]

            return sorted_views

        except Exception as e:
            logger.error(f"Failed to search views: {e}")
            return []
