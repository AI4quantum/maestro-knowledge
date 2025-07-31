# SPDX-License-Identifier: MIT
# Copyright (c) 2025 dr.max

import json
import os
import warnings
from typing import List, Dict, Any

# Suppress Pydantic deprecation warnings from dependencies
warnings.filterwarnings(
    "ignore", category=DeprecationWarning, message=".*class-based `config`.*"
)
warnings.filterwarnings(
    "ignore", category=DeprecationWarning, message=".*PydanticDeprecatedSince20.*"
)
warnings.filterwarnings(
    "ignore",
    category=DeprecationWarning,
    message=".*Support for class-based `config`.*",
)

from .vector_db_base import VectorDatabase


class MilvusVectorDatabase(VectorDatabase):
    """Milvus implementation of the vector database interface."""

    def __init__(self, collection_name: str = "MaestroDocs", dimension: int = None):
        super().__init__(collection_name)
        self.client = None
        self.collection_name = collection_name
        self.dimension = dimension
        self._client_created = False
        self.embedding_model = None  # Store the embedding model used
        print(
            f"[SERVER DEBUG] MilvusVectorDatabase initialized with dimension: {dimension}"
        )

    def supported_embeddings(self) -> List[str]:
        """
        Return a list of supported embedding model names for Milvus.

        Milvus supports both pre-computed vectors and can work with external
        embedding services, but doesn't have built-in embedding models.

        Returns:
            List of supported embedding model names
        """
        return [
            "default",
            "text-embedding-ada-002",
            "text-embedding-3-small",
            "text-embedding-3-large",
            "custom_local",
        ]

    def _ensure_client(self):
        """Ensure the client is created, handling import-time issues."""
        if not self._client_created:
            self._create_client()
            self._client_created = True

    def _create_client(self):
        import os
        import warnings

        # Temporarily unset MILVUS_URI to prevent pymilvus from auto-connecting during import
        original_milvus_uri = os.environ.pop("MILVUS_URI", None)

        try:
            # Import pymilvus after unsetting the environment variable
            from pymilvus import MilvusClient

            milvus_uri = original_milvus_uri or "milvus_demo.db"
            milvus_token = os.getenv("MILVUS_TOKEN", None)

            # For local Milvus Lite, try different URI formats
            try:
                if milvus_token:
                    self.client = MilvusClient(uri=milvus_uri, token=milvus_token)
                else:
                    self.client = MilvusClient(uri=milvus_uri)
            except Exception as e:
                # If the URI format fails, try with file:// prefix
                if not milvus_uri.startswith(("http://", "https://", "file://")):
                    file_uri = f"file://{milvus_uri}"
                    try:
                        if milvus_token:
                            self.client = MilvusClient(uri=file_uri, token=milvus_token)
                        else:
                            self.client = MilvusClient(uri=file_uri)
                    except Exception as file_e:
                        # If both attempts fail, create a mock client that warns about connection issues
                        warnings.warn(
                            f"Failed to connect to Milvus at {milvus_uri} or {file_uri}. "
                            f"Milvus operations will be disabled. Error: {file_e}"
                        )
                        self.client = None
                else:
                    # For HTTP URIs, if connection fails, create a mock client
                    warnings.warn(
                        f"Failed to connect to Milvus server at {milvus_uri}. "
                        f"Milvus operations will be disabled. Error: {e}"
                    )
                    self.client = None
        finally:
            # Restore the environment variable
            if original_milvus_uri:
                os.environ["MILVUS_URI"] = original_milvus_uri

    def _generate_embedding(self, text: str, embedding_model: str) -> List[float]:
        """
        Generate embeddings for text using the specified model.

        Args:
            text: Text to embed
            embedding_model: Name of the embedding model to use

        Returns:
            List of floats representing the embedding vector
        """
        try:
            import openai

            client_kwargs = {}
            model_to_use = embedding_model

            if embedding_model == "custom_local":
                custom_endpoint_url = os.getenv("CUSTOM_EMBEDDING_URL")
                if not custom_endpoint_url:
                    raise ValueError(
                        "CUSTOM_EMBEDDING_URL must be set for 'custom_local' embedding."
                    )

                client_kwargs["base_url"] = custom_endpoint_url
                client_kwargs["api_key"] = os.getenv(
                    "CUSTOM_EMBEDDING_API_KEY", "ollama"
                )
                model_to_use = os.getenv("CUSTOM_EMBEDDING_MODEL", "nomic-embed-text")
            else:
                # Get OpenAI API key from environment
                api_key = os.getenv("OPENAI_API_KEY")
                if not api_key:
                    raise ValueError(
                        "OPENAI_API_KEY is required for OpenAI embeddings."
                    )
                client_kwargs["api_key"] = api_key

                if model_to_use == "default":
                    model_to_use = "text-embedding-ada-002"

            client = openai.OpenAI(**client_kwargs)
            response = client.embeddings.create(model=model_to_use, input=text)

            return response.data[0].embedding

        except ImportError:
            raise ImportError(
                "openai package is required for embedding generation. Install with: pip install openai"
            )
        except Exception as e:
            raise RuntimeError(f"Failed to generate embedding: {e}")

    def _get_embedding_dimension(self, embedding_model: str) -> int:
        """
        Get the vector dimension for a given embedding model.

        Args:
            embedding_model: Name of the embedding model

        Returns:
            Vector dimension for the model. Raises ValueError if model is unknown.
        """
        # Map embedding models to their dimensions
        dimension_mapping = {
            "text-embedding-ada-002": 1536,
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
            "default": 1536,
        }

        dimension = dimension_mapping.get(embedding_model)

        # For custom models, dimension MUST be passed in __init__ if not in mapping.
        if dimension is None:
            raise ValueError(
                f"Unknown embedding model '{embedding_model}'. Please pass the 'dimension' parameter when creating the database."
            )

        return dimension

    def setup(self, embedding: str = "default"):
        """Set up Milvus collection if it doesn't exist."""

        self._ensure_client()
        if self.client is None:
            warnings.warn("Milvus client is not available. Setup skipped.")
            return

        self.embedding_model = embedding

        # If dimension is not set during initialization, infer it from the embedding model.
        if self.dimension is None:
            self.dimension = self._get_embedding_dimension(embedding)

        # Create collection if it doesn't exist

        warnings.warn(
            f"[Milvus setup] Checking collection '{self.collection_name}' (dimension={self.dimension})"
        )
        collection_exists = self.client.has_collection(self.collection_name)
        warnings.warn(f"[Milvus setup] Collection exists: {collection_exists}")

        if collection_exists:
            try:
                info = self.client.describe_collection(self.collection_name)
                warnings.warn(f"[Milvus setup] Existing collection info: {info}")
                for field in info.get("fields", []):
                    if field.get("name") == "vector":
                        existing_dim = field.get("params", {}).get("dim")
                        if existing_dim != self.dimension:
                            raise ValueError(
                                f"Dimension mismatch: existing={existing_dim}, requested={self.dimension}"
                            )
            except Exception as e:
                warnings.warn(
                    f"[Milvus setup] Could not describe existing collection: {e}"
                )

        if not collection_exists:
            if self.dimension is None:
                warnings.warn(
                    "Database was not created with a specific dimension, which is required for setup."
                )
                raise ValueError(
                    "Database was not created with a specific dimension, which is required for setup."
                )
            warnings.warn(
                f"[Milvus setup] Creating collection '{self.collection_name}' with dimension {self.dimension}"
            )
            self.client.create_collection(
                collection_name=self.collection_name,
                dimension=self.dimension,
                primary_field_name="id",
                vector_field_name="vector",
            )
            warnings.warn(
                f"[Milvus setup] Collection '{self.collection_name}' created."
            )

    def write_documents(
        self, documents: List[Dict[str, Any]], embedding: str = "default"
    ):
        """
        Write documents to Milvus.

        Args:
            documents: List of documents with 'url', 'text', and 'metadata' fields.
                      Documents may also include a 'vector' field for pre-computed embeddings.
            embedding: Embedding strategy to use:
                      - "default": Use pre-computed vector if available, otherwise use text-embedding-ada-002
                      - Specific model name: Use the specified embedding model to generate vectors

        """
        self._ensure_client()
        if self.client is None:
            warnings.warn("Milvus client is not available. Documents not written.")
            return

        # Validate embedding parameter (including custom_local)
        all_supported = self.supported_embeddings()
        if embedding not in all_supported:
            raise ValueError(
                f"Unsupported embedding: {embedding}. Supported: {all_supported}"
            )

        # Process documents
        data = []
        for i, doc in enumerate(documents):
            doc_vector = None

            # Determine how to get the vector
            if embedding == "default":
                # For default, use pre-computed vector if available

                if "vector" in doc:
                    doc_vector = doc["vector"]
                else:
                    # Generate embedding using default model
                    doc_vector = self._generate_embedding(
                        doc.get("text", ""), "text-embedding-ada-002"
                    )
            else:
                # Use specified embedding model
                doc_vector = self._generate_embedding(doc.get("text", ""), embedding)

            if doc_vector is None:
                raise ValueError(f"Failed to generate vector for document {i}")

            data.append(
                {
                    "id": i,
                    "url": doc.get("url", ""),
                    "text": doc.get("text", ""),
                    "metadata": json.dumps(doc.get("metadata", {}), ensure_ascii=False),
                    "vector": doc_vector,
                }
            )
        self.client.insert(self.collection_name, data)

    def list_documents(self, limit: int = 10, offset: int = 0) -> List[Dict[str, Any]]:
        """List documents from Milvus."""
        self._ensure_client()
        if self.client is None:
            warnings.warn("Milvus client is not available. Returning empty list.")
            return []

        # Check if collection name is set
        if self.collection_name is None:
            warnings.warn("No collection name set. Returning empty list.")
            return []

        try:
            # Query all documents, paginated
            results = self.client.query(
                self.collection_name,
                output_fields=["id", "url", "text", "metadata"],
                limit=limit,
                offset=offset,
            )

            docs = []
            for doc in results:
                try:
                    metadata = json.loads(doc.get("metadata", "{}"))
                except Exception:
                    metadata = {}
                docs.append(
                    {
                        "id": doc.get("id"),
                        "url": doc.get("url", ""),
                        "text": doc.get("text", ""),
                        "metadata": metadata,
                    }
                )
            return docs
        except Exception as e:
            warnings.warn(f"Could not list documents: {e}")
            return []

    def count_documents(self) -> int:
        """Get the current count of documents in the collection."""
        self._ensure_client()
        if self.client is None:
            warnings.warn("Milvus client is not available. Returning 0.")
            return 0

        # Check if collection name is set
        if self.collection_name is None:
            warnings.warn("No collection name set. Returning 0.")
            return 0

        try:
            # Get collection statistics
            stats = self.client.get_collection_stats(self.collection_name)
            return stats.get("row_count", 0)
        except Exception as e:
            warnings.warn(f"Could not get collection stats: {e}")
            return 0

    def list_collections(self) -> List[str]:
        """List all collections in Milvus."""
        self._ensure_client()
        if self.client is None:
            warnings.warn("Milvus client is not available. Returning empty list.")
            return []

        try:
            # Get all collections from the client
            collections = self.client.list_collections()
            return collections
        except Exception as e:
            warnings.warn(f"Could not list collections from Milvus: {e}")
            return []

    def list_documents_in_collection(
        self, collection_name: str, limit: int = 10, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """List documents from a specific collection in Milvus."""
        self._ensure_client()
        if self.client is None:
            warnings.warn("Milvus client is not available. Returning empty list.")
            return []

        try:
            # Check if collection exists first
            if not self.client.has_collection(collection_name):
                return []

            # Query documents from the specific collection
            results = self.client.query(
                collection_name,
                output_fields=["id", "url", "text", "metadata"],
                limit=limit,
                offset=offset,
            )

            docs = []
            for doc in results:
                try:
                    metadata = json.loads(doc.get("metadata", "{}"))
                except Exception:
                    metadata = {}
                docs.append(
                    {
                        "id": doc.get("id"),
                        "url": doc.get("url", ""),
                        "text": doc.get("text", ""),
                        "metadata": metadata,
                    }
                )
            return docs
        except Exception as e:
            warnings.warn(
                f"Could not list documents from collection '{collection_name}': {e}"
            )
            return []

    def count_documents_in_collection(self, collection_name: str) -> int:
        """Get the current count of documents in a specific collection in Milvus."""
        self._ensure_client()
        if self.client is None:
            warnings.warn("Milvus client is not available. Returning 0.")
            return 0

        try:
            # Check if collection exists first
            if not self.client.has_collection(collection_name):
                return 0

            # Get collection statistics for the specific collection
            stats = self.client.get_collection_stats(collection_name)
            return stats.get("row_count", 0)
        except Exception as e:
            warnings.warn(
                f"Could not get collection stats for '{collection_name}': {e}"
            )
            return 0

    def get_document(
        self, doc_name: str, collection_name: str = None
    ) -> Dict[str, Any]:
        """Get a specific document by name from a collection in Milvus."""
        self._ensure_client()
        if self.client is None:
            raise ValueError("Milvus client is not available")

        target_collection = collection_name or self.collection_name

        try:
            # Check if collection exists first
            if not self.client.has_collection(target_collection):
                raise ValueError(f"Collection '{target_collection}' not found")

            # Query for the specific document by doc_name in metadata
            results = self.client.query(
                target_collection,
                filter=f'metadata["doc_name"] == "{doc_name}"',
                output_fields=["id", "url", "text", "metadata"],
                limit=1,
            )

            if not results:
                raise ValueError(
                    f"Document '{doc_name}' not found in collection '{target_collection}'"
                )

            doc = results[0]
            try:
                metadata = json.loads(doc.get("metadata", "{}"))
            except Exception:
                metadata = {}

            return {
                "id": doc.get("id"),
                "url": doc.get("url", ""),
                "text": doc.get("text", ""),
                "metadata": metadata,
            }
        except ValueError as e:
            # Re-raise ValueError as is (these are user-friendly error messages)
            raise e
        except Exception as e:
            raise ValueError(f"Failed to retrieve document '{doc_name}': {e}")

    def get_collection_info(self, collection_name: str = None) -> Dict[str, Any]:
        """Get detailed information about a collection."""
        self._ensure_client()
        if self.client is None:
            warnings.warn("Milvus client is not available. Returning empty info.")
            return {
                "name": collection_name or self.collection_name,
                "document_count": 0,
                "db_type": "milvus",
                "embedding": "unknown",
                "metadata": {},
            }

        target_collection = collection_name or self.collection_name

        try:
            # Check if collection exists
            if not self.client.has_collection(target_collection):
                return {
                    "name": target_collection,
                    "document_count": 0,
                    "db_type": "milvus",
                    "embedding": "unknown",
                    "metadata": {"error": "Collection does not exist"},
                }

            # Get collection statistics
            stats = self.client.get_collection_stats(target_collection)
            document_count = stats.get("row_count", 0)

            # Get collection schema information
            collection_info = self.client.describe_collection(target_collection)

            # Use stored embedding model if available, otherwise try to extract from schema
            if self.embedding_model:
                embedding_info = self.embedding_model
            else:
                embedding_info = "unknown"
                if hasattr(collection_info, "fields"):
                    for field in collection_info.fields:
                        if field.name == "vector":
                            embedding_info = (
                                f"vector_dim_{field.params.get('dim', 'unknown')}"
                            )
                            break

            return {
                "name": target_collection,
                "document_count": document_count,
                "db_type": "milvus",
                "embedding": embedding_info,
                "metadata": {
                    "collection_id": collection_info.id
                    if hasattr(collection_info, "id")
                    else None,
                    "created_time": collection_info.created_time
                    if hasattr(collection_info, "created_time")
                    else None,
                    "description": collection_info.description
                    if hasattr(collection_info, "description")
                    else None,
                    "fields_count": len(collection_info.fields)
                    if hasattr(collection_info, "fields")
                    else 0,
                },
            }
        except Exception as e:
            warnings.warn(f"Could not get collection info from Milvus: {e}")
            return {
                "name": target_collection,
                "document_count": 0,
                "db_type": "milvus",
                "embedding": "unknown",
                "metadata": {"error": str(e)},
            }

    def delete_documents(self, document_ids: List[str]):
        """Delete documents from Milvus by their IDs."""
        self._ensure_client()
        if self.client is None:
            warnings.warn("Milvus client is not available. Documents not deleted.")
            return

        # Convert string IDs to integers for Milvus
        try:
            int_ids = [int(doc_id) for doc_id in document_ids]
        except ValueError:
            raise ValueError("Milvus document IDs must be convertible to integers.")

        # Delete documents by ID
        self.client.delete(self.collection_name, ids=int_ids)

    def delete_collection(self, collection_name: str = None):
        """Delete an entire collection from Milvus."""
        self._ensure_client()
        if self.client is None:
            warnings.warn("Milvus client is not available. Collection not deleted.")
            return

        target_collection = collection_name or self.collection_name

        if self.client.has_collection(target_collection):
            self.client.drop_collection(target_collection)
            if target_collection == self.collection_name:
                self.collection_name = None

    def create_query_agent(self):
        """Create a query agent for Milvus."""
        # Placeholder: Milvus does not have a built-in query agent like Weaviate
        # You would implement your own search logic here
        return self

    def cleanup(self):
        """Clean up Milvus client."""
        if self.client is not None:
            if self.collection_name:
                if self.client.has_collection(self.collection_name):
                    self.client.drop_collection(self.collection_name)
        self.client = None

    @property
    def db_type(self) -> str:
        return "milvus"
