# SPDX-License-Identifier: Apache 2.0
# Copyright (c) 2025 IBM

import json
import logging
import warnings
from typing import Any

import weaviate

logger = logging.getLogger(__name__)

# Suppress all deprecation warnings from external packages immediately
warnings.filterwarnings("ignore", category=DeprecationWarning)

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

from src.chunking import ChunkingConfig, chunk_text

from .vector_db_base import VectorDatabase


class WeaviateVectorDatabase(VectorDatabase):
    """Weaviate implementation of the vector database interface."""

    def __init__(self, collection_name: str = "MaestroDocs") -> None:
        super().__init__(collection_name)
        self.client = None
        self.embedding_model = None  # Store the embedding model used
        self._create_client()

    def supported_embeddings(self) -> list[str]:
        """
        Return a list of supported embedding model names for Weaviate.

        Weaviate supports various vectorizers and can also work with external
        embedding services.

        Returns:
            List of supported embedding model names
        """
        return [
            "default",  # Uses text2vec-weaviate
            "text2vec-weaviate",
            "text2vec-openai",
            "text2vec-cohere",
            "text2vec-huggingface",
            "text-embedding-ada-002",
            "text-embedding-3-small",
            "text-embedding-3-large",
        ]

    def _create_client(self) -> None:
        """Create the Weaviate client."""
        import os

        import weaviate
        from weaviate.auth import Auth

        weaviate_api_key = os.getenv("WEAVIATE_API_KEY")
        weaviate_url = os.getenv("WEAVIATE_URL")
        openai_api_key = os.getenv("OPENAI_APIKEY") or os.getenv("OPENAI_API_KEY")

        if not weaviate_api_key:
            raise ValueError("WEAVIATE_API_KEY is not set")
        if not weaviate_url:
            raise ValueError("WEAVIATE_URL is not set")

        # Set OpenAI API key in environment if available
        if openai_api_key:
            os.environ["OPENAI_APIKEY"] = openai_api_key

        self.client = weaviate.use_async_with_weaviate_cloud(
            cluster_url=weaviate_url,
            auth_credentials=Auth.api_key(weaviate_api_key),
        )

    def _get_vectorizer_config(
        self, embedding: str
    ) -> weaviate.classes.config.Configure.Vectorizer:
        """
        Get the appropriate vectorizer configuration for the embedding model.

        Args:
            embedding: Name of the embedding model to use

        Returns:
            Vectorizer configuration object
        """
        from weaviate.classes.config import Configure

        # Map embedding names to Weaviate vectorizer configurations
        vectorizer_mapping = {
            "default": Configure.Vectorizer.text2vec_weaviate(),
            "text2vec-weaviate": Configure.Vectorizer.text2vec_weaviate(),
            "text2vec-openai": Configure.Vectorizer.text2vec_openai(
                model="text-embedding-ada-002",
                model_version="002",
                type_="text",
                vectorize_collection_name=False,
            ),
            "text2vec-cohere": Configure.Vectorizer.text2vec_cohere(
                model="embed-multilingual-v3.0", vectorize_collection_name=False
            ),
            "text2vec-huggingface": Configure.Vectorizer.text2vec_huggingface(
                model="sentence-transformers/all-MiniLM-L6-v2",
                vectorize_collection_name=False,
            ),
        }

        # For OpenAI embedding models, use text2vec-openai with appropriate model
        if embedding in [
            "text-embedding-ada-002",
            "text-embedding-3-small",
            "text-embedding-3-large",
        ]:
            return Configure.Vectorizer.text2vec_openai(
                model=embedding,
                vectorize_collection_name=False,
            )

        if embedding not in vectorizer_mapping:
            raise ValueError(
                f"Unsupported embedding: {embedding}. Supported: {self.supported_embeddings()}"
            )

        return vectorizer_mapping[embedding]

    async def setup(
        self,
        embedding: str = "default",
        collection_name: str = None,
        chunking_config: dict[str, Any] = None,
    ) -> None:
        """
        Set up Weaviate collection if it doesn't exist.

        Args:
            embedding: Embedding model to use for the collection
            collection_name: Name of the collection to set up (defaults to self.collection_name)
        """
        from weaviate.classes.config import DataType, Property

        # Use the specified collection name or fall back to the default
        target_collection = (
            collection_name if collection_name is not None else self.collection_name
        )

        # Store the embedding model
        self.embedding_model = embedding

        # Track collection metadata including chunking
        if not hasattr(self, "_collections_metadata"):
            self._collections_metadata = {}
        target_meta = {
            "embedding": embedding,
            "chunking": chunking_config or {"strategy": "None", "parameters": {}},
        }
        self._collections_metadata[target_collection] = target_meta
        await self.client.connect()
        if not await self.client.collections.exists(target_collection):
            vectorizer_config = self._get_vectorizer_config(embedding)

            await self.client.collections.create(
                target_collection,
                description="A dataset with the contents of Maestro Knowledge docs and website",
                vectorizer_config=vectorizer_config,
                properties=[
                    Property(
                        name="url",
                        data_type=DataType.TEXT,
                        description="the source URL of the webpage",
                    ),
                    Property(
                        name="text",
                        data_type=DataType.TEXT,
                        description="the content of the webpage",
                    ),
                    Property(
                        name="metadata",
                        data_type=DataType.TEXT,
                        description="additional metadata in JSON format",
                    ),
                ],
            )
            # Optionally store meta in client if supported
            try:
                if hasattr(self.client.collections, "set_metadata"):
                    await self.client.collections.set_metadata(
                        target_collection, self._collections_metadata[target_collection]
                    )
            except Exception:
                pass

    async def write_documents(
        self,
        documents: list[dict[str, Any]],
        embedding: str = "default",
        collection_name: str = None,
    ) -> dict[str, Any]:
        # TODO(embedding): Per-write 'embedding' parameter is deprecated. Collection-level embedding
        #                  set via setup() should be used. This parameter will be removed or ignored in a future release.
        """
        Write documents to Weaviate.

        Args:
            documents: List of documents with 'url', 'text', and 'metadata' fields
            embedding: Embedding strategy to use:
                      - "default": Use Weaviate's default text2vec-weaviate
                      - Specific model name: Use the specified embedding model
            collection_name: Name of the collection to write to (defaults to self.collection_name)
        """
        # Use the specified collection name or fall back to the default
        target_collection = (
            collection_name if collection_name is not None else self.collection_name
        )

        # Validate embedding parameter but prefer collection-level embedding
        if embedding not in self.supported_embeddings():
            raise ValueError(
                f"Unsupported embedding: {embedding}. Supported: {self.supported_embeddings()}"
            )

        # Ensure collection exists with the correct embedding configuration
        if not await self.client.collections.exists(target_collection):
            await self.setup(embedding, target_collection)

        # If the collection has an embedding set and the caller provided a different one,
        # ignore the per-write parameter and warn (deprecation path).
        if self.embedding_model and embedding not in ("default", self.embedding_model):
            warnings.warn(
                "Embedding model should be configured per-collection. The per-write 'embedding' parameter is ignored.",
                stacklevel=2,
            )

        collection = await self.client.collections.get(target_collection)
        # Determine chunking config for this collection
        coll_meta = getattr(self, "_collections_metadata", {}).get(
            target_collection, {}
        )
        chunking_conf = coll_meta.get("chunking") if coll_meta else None

        # Collect lightweight stats similar to Milvus implementation
        import time

        stats_per_doc: list[dict[str, Any]] = []
        total_chunks = 0
        build_start = time.perf_counter()

        # Process documents to ensure they have text content
        processed_documents = []
        for doc in documents:
            try:
                processed_doc = await self._ensure_document_content(doc)
                processed_documents.append(processed_doc)
            except Exception as e:
                logger.warning(
                    f"Failed to process document {doc.get('url', 'unknown')}: {e}"
                )
                # Skip documents that fail to process
                continue

        try:
            with await collection.batch.dynamic() as batch:
                for idx, doc in enumerate(processed_documents):
                    doc_start = time.perf_counter()
                    orig_metadata = dict(doc.get("metadata", {}))
                    text = doc.get("text", "")

                    cfg = ChunkingConfig(
                        strategy=(chunking_conf or {}).get("strategy", "None"),
                        parameters=(chunking_conf or {}).get("parameters", {}),
                    )
                    chunks = chunk_text(text, cfg)

                    per_doc_chunk_count = 0
                    per_doc_char_count = 0

                    for chunk in chunks:
                        new_meta = dict(orig_metadata)
                        if "doc_name" in orig_metadata:
                            new_meta["doc_name"] = orig_metadata.get("doc_name")
                        # omit chunking policy to reduce per-result duplication
                        new_meta.update(
                            {
                                "chunk_sequence_number": int(chunk["sequence"]),
                                "total_chunks": int(chunk["total"]),
                                "offset_start": int(chunk["offset_start"]),
                                "offset_end": int(chunk["offset_end"]),
                                "chunk_size": int(chunk["chunk_size"]),
                            }
                        )
                        per_doc_chunk_count += 1
                        per_doc_char_count += len(chunk.get("text", "") or "")

                        metadata_text = json.dumps(new_meta, ensure_ascii=False)
                        batch.add_object(
                            properties={
                                "url": doc.get("url", ""),
                                "text": chunk["text"],
                                "metadata": metadata_text,
                            }
                        )

                    total_chunks += per_doc_chunk_count
                    stats_per_doc.append(
                        {
                            "name": orig_metadata.get("doc_name")
                            or doc.get("url")
                            or f"doc_{idx}",
                            "chunk_count": per_doc_chunk_count,
                            "char_count": per_doc_char_count,
                            "duration_ms": int(
                                (time.perf_counter() - doc_start) * 1000
                            ),
                        }
                    )
            # Check for errors after the batch operation
            if batch.failed_objects:
                error_messages = []
                for failed_obj in batch.failed_objects:
                    error_messages.append(
                        f"Failed to import object: {failed_obj.object_} - Error: {failed_obj.message}"
                    )
                raise RuntimeError(
                    f"Weaviate batch import failed for some objects: {'; '.join(error_messages)}"
                )
            if batch.failed_references:
                error_messages = []
                for failed_ref in batch.failed_references:
                    error_messages.append(
                        f"Failed to import reference: {failed_ref.reference_} - Error: {failed_ref.message}"
                    )
                raise RuntimeError(
                    f"Weaviate batch import failed for some references: {'; '.join(error_messages)}"
                )
        except Exception as e:
            raise RuntimeError(f"Error during Weaviate batch import: {e}") from e

        total_duration_ms = int((time.perf_counter() - build_start) * 1000)

        return {
            "backend": "weaviate",
            "documents": len(documents),
            "chunks": total_chunks,
            "per_document": stats_per_doc,
            "insert_ms": None,  # not available from client batch API
            "duration_ms": total_duration_ms,
        }

    async def write_documents_to_collection(
        self,
        documents: list[dict[str, Any]],
        collection_name: str,
        embedding: str = "default",
    ) -> dict[str, Any]:
        """
        Write documents to a specific collection in Weaviate.

        Args:
            documents: List of documents with 'url', 'text', and 'metadata' fields
            collection_name: Name of the collection to write to
            embedding: Embedding strategy to use:
                      - "default": Use Weaviate's default text2vec-weaviate
                      - Specific model name: Use the specified embedding model
        """
        return await self.write_documents(documents, embedding, collection_name)

    async def list_documents(
        self, limit: int = 10, offset: int = 0
    ) -> list[dict[str, Any]]:
        """List documents from Weaviate."""
        collection = await self.client.collections.get(self.collection_name)

        # Query the collection
        result = await collection.query.fetch_objects(
            limit=limit,
            offset=offset,
            include_vector=False,  # Don't include vector data in response
        )

        # Process the results
        documents = []
        for obj in result.objects:
            doc = {
                "id": obj.uuid,
                "url": obj.properties.get("url", ""),
                "text": obj.properties.get("text", ""),
                "metadata": obj.properties.get("metadata", "{}"),
            }

            # Try to parse metadata if it's a JSON string
            try:
                doc["metadata"] = json.loads(doc["metadata"])
            except json.JSONDecodeError:
                pass

            documents.append(doc)

        return documents

    async def list_documents_in_collection(
        self, collection_name: str, limit: int = 10, offset: int = 0
    ) -> list[dict[str, Any]]:
        """List documents from a specific collection in Weaviate."""
        try:
            # Get the specific collection
            collection = await self.client.collections.get(collection_name)

            # Query documents from the collection
            result = await collection.query.fetch_objects(
                limit=limit,
                offset=offset,
                include_vector=False,
            )

            # Process the results
            documents = []
            for obj in result.objects:
                doc = {
                    "id": obj.uuid,
                    "url": obj.properties.get("url", ""),
                    "text": obj.properties.get("text", ""),
                    "metadata": obj.properties.get("metadata", "{}"),
                }

                # Try to parse metadata if it's a JSON string
                try:
                    doc["metadata"] = json.loads(doc["metadata"])
                except json.JSONDecodeError:
                    pass

                documents.append(doc)

            return documents
        except Exception as e:
            warnings.warn(
                f"Could not list documents from Weaviate collection '{collection_name}': {e}"
            )
            return []

    async def count_documents_in_collection(self, collection_name: str) -> int:
        """Get the current count of documents in a specific collection in Weaviate."""
        try:
            # Get the specific collection
            collection = await self.client.collections.get(collection_name)

            # Query to get the count - use a simple approach
            result = await collection.query.fetch_objects(limit=10000)
            return len(result.objects)
        except Exception as e:
            warnings.warn(
                f"Could not get document count for Weaviate collection '{collection_name}': {e}"
            )
            return 0

    async def get_document(
        self, doc_name: str, collection_name: str = None
    ) -> dict[str, Any]:
        """Reassemble a document from its chunks by doc_name."""
        target_collection = collection_name or self.collection_name
        # Ensure collection exists
        if not await self.client.collections.exists(target_collection):
            raise ValueError(f"Collection '{target_collection}' not found")

        # Fetch all objects with metadata containing the doc_name
        collection = await self.client.collections.get(target_collection)
        filter_property = await collection.query.filter.by_property("metadata")
        filter_condition = await filter_property.contains_any([doc_name])
        result = await collection.query.fetch_objects(
            where=filter_condition,
            limit=10000,
        )

        chunks = []
        for obj in result.objects:
            metadata = obj.properties.get("metadata", {})
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except Exception:
                    metadata = {}
            if isinstance(metadata, dict) and metadata.get("doc_name") == doc_name:
                chunks.append(
                    {
                        "id": obj.uuid,
                        "url": obj.properties.get("url", ""),
                        "text": obj.properties.get("text", ""),
                        "metadata": metadata,
                    }
                )

        doc = self._reassemble_chunks_into_document(chunks)
        if doc is None:
            # If no chunks or unable to reassemble, raise document-not-found with collection context
            raise ValueError(
                f"Document '{doc_name}' not found in collection '{target_collection}'"
            )
        return doc

    async def get_document_chunks(
        self, doc_id: str, collection_name: str = None
    ) -> list[dict[str, Any]]:
        target_collection = collection_name or self.collection_name
        collection = await self.client.collections.get(target_collection)
        filter_property = await collection.query.filter.by_property("metadata")
        filter_condition = await filter_property.contains_any([doc_id])
        result = await collection.query.fetch_objects(
            where=filter_condition,
            limit=10000,
        )
        chunks = []
        for obj in result.objects:
            metadata = obj.properties.get("metadata", {})
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except Exception:
                    metadata = {}
            if isinstance(metadata, dict) and metadata.get("doc_name") == doc_id:
                chunks.append(
                    {
                        "id": obj.uuid,
                        "url": obj.properties.get("url", ""),
                        "text": obj.properties.get("text", ""),
                        "metadata": metadata,
                    }
                )
        return chunks

    async def count_documents(self) -> int:
        """Get the current count of documents in the collection."""
        collection = await self.client.collections.get(self.collection_name)

        # Query to get the count - use a simple approach
        try:
            # Get all objects and count them (with a reasonable limit)
            result = await collection.query.fetch_objects(limit=10000)
            return len(result.objects)
        except Exception as e:
            # If we can't get the count, return 0
            import warnings

            warnings.warn(f"Could not get document count for Weaviate collection: {e}")
            return 0

    async def list_collections(self) -> list[str]:
        """List all collections in Weaviate."""
        try:
            # Ensure client is connected
            await self.client.connect()

            # Get all collections from the client
            collections = await self.client.collections.list_all()

            # Handle both object collections and string collections
            collection_names = []
            for collection in collections:
                if hasattr(collection, "name"):
                    collection_names.append(collection.name)
                elif isinstance(collection, str):
                    collection_names.append(collection)
                else:
                    # Try to get the name as a property
                    collection_names.append(str(collection))

            return collection_names
        except Exception as e:
            warnings.warn(f"Could not list collections from Weaviate: {e}")
            return []

    async def get_collection_info(self, collection_name: str = None) -> dict[str, Any]:
        """Get detailed information about a collection."""
        target_collection = collection_name or self.collection_name

        try:
            # Check if collection exists
            if not await self.client.collections.exists(target_collection):
                return {
                    "name": target_collection,
                    "document_count": 0,
                    "db_type": "weaviate",
                    "embedding": "unknown",
                    "chunking": getattr(self, "_collections_metadata", {})
                    .get(target_collection, {})
                    .get("chunking"),
                    "embedding_details": {
                        "name": self.embedding_model or "unknown",
                        "vector_size": None,  # unknown from API
                        "provider": (
                            "openai"
                            if (
                                self.embedding_model
                                in {
                                    "text-embedding-ada-002",
                                    "text-embedding-3-small",
                                    "text-embedding-3-large",
                                    "text2vec-openai",
                                }
                            )
                            else (
                                "weaviate"
                                if (
                                    self.embedding_model
                                    in {"default", "text2vec-weaviate"}
                                )
                                else (
                                    "cohere"
                                    if self.embedding_model == "text2vec-cohere"
                                    else (
                                        "huggingface"
                                        if self.embedding_model
                                        == "text2vec-huggingface"
                                        else "unknown"
                                    )
                                )
                            )
                        ),
                        "source": "collection" if self.embedding_model else "unknown",
                    },
                    "metadata": {"error": "Collection does not exist"},
                }

            # Get collection object
            collection = await self.client.collections.get(target_collection)

            # Get document count
            try:
                result = await collection.query.fetch_objects(limit=10000)
                document_count = len(result.objects)
            except Exception as e:
                import warnings

                warnings.warn(
                    f"Could not get document count for Weaviate collection: {e}"
                )
                document_count = 0

            # Get collection configuration
            config = collection.config.get()

            # Use stored embedding model if available, otherwise try to extract from config
            if self.embedding_model:
                embedding_info = self.embedding_model
            else:
                embedding_info = "unknown"
                if hasattr(config, "vectorizer") and config.vectorizer:
                    embedding_info = config.vectorizer
                elif hasattr(config, "vectorizer_config") and config.vectorizer_config:
                    embedding_info = str(config.vectorizer_config)

            # Get additional metadata
            metadata = {
                "description": config.description
                if hasattr(config, "description")
                else None,
                "vectorizer": config.vectorizer
                if hasattr(config, "vectorizer")
                else None,
                "properties_count": len(config.properties)
                if hasattr(config, "properties")
                else 0,
                "module_config": config.module_config
                if hasattr(config, "module_config")
                else None,
            }

            # Attempt to include configured chunking metadata if tracked
            chunking_conf = (
                getattr(self, "_collections_metadata", {})
                .get(target_collection, {})
                .get("chunking")
            )

            # Build embedding details
            provider = (
                "openai"
                if (
                    embedding_info
                    in {
                        "text-embedding-ada-002",
                        "text-embedding-3-small",
                        "text-embedding-3-large",
                        "text2vec-openai",
                    }
                    or self.embedding_model
                    in {
                        "text-embedding-ada-002",
                        "text-embedding-3-small",
                        "text-embedding-3-large",
                        "text2vec-openai",
                    }
                )
                else (
                    "weaviate"
                    if (
                        embedding_info in {"default", "text2vec-weaviate"}
                        or self.embedding_model in {"default", "text2vec-weaviate"}
                    )
                    else (
                        "cohere"
                        if (
                            embedding_info == "text2vec-cohere"
                            or self.embedding_model == "text2vec-cohere"
                        )
                        else (
                            "huggingface"
                            if (
                                embedding_info == "text2vec-huggingface"
                                or self.embedding_model == "text2vec-huggingface"
                            )
                            else "unknown"
                        )
                    )
                )
            )

            return {
                "name": target_collection,
                "document_count": document_count,
                "db_type": "weaviate",
                "embedding": embedding_info,
                "chunking": chunking_conf,
                "embedding_details": {
                    "name": self.embedding_model or embedding_info,
                    "vector_size": None,  # unknown from Weaviate API
                    "provider": provider,
                    "source": "collection" if self.embedding_model else "config",
                },
                "metadata": metadata,
            }
        except Exception as e:
            warnings.warn(f"Could not get collection info from Weaviate: {e}")
            provider = (
                "openai"
                if (
                    self.embedding_model
                    in {
                        "text-embedding-ada-002",
                        "text-embedding-3-small",
                        "text-embedding-3-large",
                        "text2vec-openai",
                    }
                )
                else (
                    "weaviate"
                    if (self.embedding_model in {"default", "text2vec-weaviate"})
                    else (
                        "cohere"
                        if self.embedding_model == "text2vec-cohere"
                        else (
                            "huggingface"
                            if self.embedding_model == "text2vec-huggingface"
                            else "unknown"
                        )
                    )
                )
            )
            return {
                "name": target_collection,
                "document_count": 0,
                "db_type": "weaviate",
                "embedding": "unknown",
                "chunking": getattr(self, "_collections_metadata", {})
                .get(target_collection, {})
                .get("chunking"),
                "embedding_details": {
                    "name": self.embedding_model or "unknown",
                    "vector_size": None,
                    "provider": provider,
                    "source": "collection" if self.embedding_model else "unknown",
                },
                "metadata": {"error": str(e)},
            }

    async def delete_documents(self, document_ids: list[str]) -> None:
        """Delete documents from Weaviate by their IDs."""
        collection = await self.client.collections.get(self.collection_name)

        # Delete documents by UUID
        for doc_id in document_ids:
            try:
                await collection.data.delete_by_id(doc_id)
            except Exception as e:
                warnings.warn(f"Failed to delete document {doc_id}: {e}")

    async def delete_collection(self, collection_name: str = None) -> None:
        """Delete an entire collection from Weaviate."""
        target_collection = collection_name or self.collection_name

        try:
            if await self.client.collections.exists(target_collection):
                await self.client.collections.delete(target_collection)
                if target_collection == self.collection_name:
                    self.collection_name = None
        except Exception as e:
            warnings.warn(f"Failed to delete collection {target_collection}: {e}")

    # TODO: Type needs consideration

    def create_query_agent(self) -> "QueryAgent":
        """Create a Weaviate query agent."""
        from weaviate.agents.query import QueryAgent

        return QueryAgent(client=self.client, collections=[self.collection_name])

    async def query(
        self, query: str, limit: int = 5, collection_name: str = None
    ) -> str:
        """
        Query the vector database using Weaviate's vector similarity search.

        Args:
            query: The query string to search for
            limit: Maximum number of results to consider
            collection_name: Optional collection name to search in (defaults to self.collection_name)

        Returns:
            A string response with relevant information from the database
        """
        try:
            # Use vector similarity search as the primary method
            documents = await self.search(query, limit, collection_name)

            if not documents:
                return f"No relevant documents found for query: '{query}'"

            # Format the results
            response_parts = [
                f"Found {len(documents)} relevant documents for query: '{query}'\n\n"
            ]

            for i, doc in enumerate(documents, 1):
                response_parts.append(f"Document {i}:")
                response_parts.append(f"  URL: {doc.get('url', 'N/A')}")
                response_parts.append(f"  Text: {doc.get('text', 'N/A')[:200]}...")
                response_parts.append("")

            return "\n".join(response_parts)

        except Exception as e:
            warnings.warn(f"Failed to query Weaviate: {e}")
            return f"Error querying database: {str(e)}"

    async def search(
        self, query: str, limit: int = 5, collection_name: str = None
    ) -> list[dict[str, Any]]:
        """
        Search for documents using Weaviate's vector similarity search.

        Args:
            query: The search query text
            limit: Maximum number of results to return
            collection_name: Optional collection name to search in (defaults to self.collection_name)

        Returns:
            List of documents sorted by relevance
        """
        try:
            target_collection = (
                collection_name if collection_name is not None else self.collection_name
            )
            collection = await self.client.collections.get(target_collection)

            # Use Weaviate's near_text search for vector similarity and request scoring metadata
            try:
                from weaviate.classes.query import MetadataQuery

                metadata_query = MetadataQuery(distance=True, score=True)
            except (ImportError, AttributeError):
                # If MetadataQuery isn't available, proceed without explicit scoring
                metadata_query = None

            if metadata_query is not None:
                result = await collection.query.near_text(
                    query=query,
                    limit=limit,
                    include_vector=False,
                    return_metadata=metadata_query,
                )
            else:
                result = await collection.query.near_text(
                    query=query,
                    limit=limit,
                    include_vector=False,
                )

            documents = []
            for idx, obj in enumerate(result.objects, start=1):
                # Try to obtain scoring info if the client provided it
                score_val = None
                distance_val = None
                try:
                    # Newer clients expose score/distance on metadata
                    if hasattr(obj, "metadata") and obj.metadata is not None:
                        # Attribute or dict access depending on client version
                        md = obj.metadata
                        score_val = getattr(md, "score", None)
                        if score_val is None and isinstance(md, dict):
                            score_val = md.get("score")
                        distance_val = getattr(md, "distance", None)
                        if distance_val is None and isinstance(md, dict):
                            distance_val = md.get("distance")
                except (AttributeError, TypeError, ValueError):
                    score_val = None
                    distance_val = None

                doc = {
                    "id": obj.uuid,
                    "url": obj.properties.get("url", ""),
                    "text": obj.properties.get("text", ""),
                    "metadata": obj.properties.get("metadata", "{}"),
                }

                # Normalized scoring fields
                # Always mark search mode and metric where known (Weaviate default vectorizer uses cosine)
                doc["_search_mode"] = "vector"
                doc["_metric"] = "cosine"

                # Do not include raw_* fields in output; we keep a normalized view only

                # Compute normalized similarity [0,1] and distance if possible
                similarity = None
                distance = None
                try:
                    if distance_val is not None:
                        distance = float(distance_val)
                        # For cosine, distance ~ 1 - similarity
                        similarity = max(0.0, min(1.0, 1.0 - distance))
                    elif score_val is not None:
                        s = float(score_val)
                        if 0.0 <= s <= 1.000001:
                            # Treat as similarity
                            similarity = max(0.0, min(1.0, s))
                            distance = 1.0 - similarity
                        elif 1.0 < s <= 2.000001:
                            # Treat as cosine distance
                            distance = s
                            similarity = max(0.0, min(1.0, 1.0 - s))
                        else:
                            # Unknown scale; leave normalized fields unset
                            pass
                except Exception:
                    pass

                if distance is not None:
                    doc["distance"] = distance
                if similarity is not None:
                    # Provide normalized similarity only (single canonical score)
                    doc["similarity"] = similarity

                # Rank within this result set (1-based)
                doc["rank"] = idx

                # Try to parse metadata if it's a JSON string
                try:
                    import json

                    doc["metadata"] = json.loads(doc["metadata"])
                except (json.JSONDecodeError, TypeError):
                    pass

                # Drop verbose chunking policy from per-result metadata to reduce duplication
                try:
                    if (
                        isinstance(doc.get("metadata"), dict)
                        and "chunking" in doc["metadata"]
                    ):
                        doc["metadata"].pop("chunking", None)
                    # Backward-compat: if old key exists, mirror to new key
                    # no remapping; keep original key only
                except Exception:
                    pass

                documents.append(doc)

            return documents

        except Exception as e:
            warnings.warn(f"Failed to perform vector search for query '{query}': {e}")
            # Fallback to simple keyword matching if vector search fails
            return await self._fallback_keyword_search(query, limit, collection_name)

    async def _fallback_keyword_search(
        self, query: str, limit: int = 5, collection_name: str = None
    ) -> list[dict[str, Any]]:
        """
        Fallback to simple keyword matching if vector search fails.

        Args:
            query: The search query text
            limit: Maximum number of results to return
            collection_name: Optional collection name to search in (defaults to self.collection_name)

        Returns:
            List of documents sorted by relevance
        """
        try:
            # Get all documents and perform keyword matching
            target_collection = (
                collection_name if collection_name is not None else self.collection_name
            )
            documents = await self.list_documents_in_collection(
                target_collection, limit=100, offset=0
            )

            query_lower = query.lower()
            query_words = query_lower.split()
            relevant_docs = []

            for doc in documents:
                text = doc.get("text", "").lower()
                url = doc.get("url", "").lower()
                metadata = doc.get("metadata", {})
                metadata_text = str(metadata).lower()

                # Count how many query words match
                matches = 0
                for word in query_words:
                    if word in text or word in url or word in metadata_text:
                        matches += 1

                # If at least one word matches, consider it relevant
                if matches > 0:
                    relevant_docs.append(
                        {"doc": doc, "matches": matches, "text_length": len(text)}
                    )

            if relevant_docs:
                # Sort by relevance (more matches first, then by text length)
                relevant_docs.sort(key=lambda x: (-x["matches"], -x["text_length"]))

                # Return the top results
                docs = [item["doc"] for item in relevant_docs[:limit]]
                # Normalize: mark keyword mode and add rank
                for i, d in enumerate(docs, start=1):
                    try:
                        d["_search_mode"] = "keyword"
                        d["rank"] = i
                        # Also remove chunking policy from metadata in fallback results
                        if (
                            isinstance(d.get("metadata"), dict)
                            and "chunking" in d["metadata"]
                        ):
                            d["metadata"].pop("chunking", None)
                    except Exception:
                        pass
                return docs

            return []

        except Exception as e:
            warnings.warn(f"Fallback keyword search also failed: {e}")
            return []

    async def cleanup(self) -> None:
        """Clean up Weaviate client."""
        if self.client:
            try:
                # Close any open connections
                if hasattr(self.client, "close"):
                    await self.client.close()
                # Also try to close the underlying connection if it exists
                if hasattr(self.client, "_connection") and self.client._connection:
                    if hasattr(self.client._connection, "close"):
                        try:
                            await self.client._connection.close()
                        except TypeError:
                            # Some connection objects don't take arguments
                            pass
            except Exception as e:
                # Log the error but don't raise it to avoid breaking shutdown
                warnings.warn(f"Error during Weaviate cleanup: {e}")
            finally:
                self.client = None

    @property
    def db_type(self) -> str:
        return "weaviate"
