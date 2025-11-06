# SPDX-License-Identifier: Apache 2.0
# Copyright (c) 2025 IBM

import json
import asyncio
import logging
import os
import time
import warnings
from typing import Any

from src.chunking import ChunkingConfig, chunk_text

# Suppress Pydantic deprecation warnings from dependencies
warnings.filterwarnings(
    "ignore", category=DeprecationWarning, message=".*class-based `config`.*"
)
warnings.filterwarnings(
    "ignore", category=DeprecationWarning, message=".*PydanticDeprecatedSince20.*"
)

logger = logging.getLogger(__name__)
warnings.filterwarnings(
    "ignore",
    category=DeprecationWarning,
    message=".*Support for class-based `config`.*",
)

from .vector_db_base import VectorDatabase


class MilvusVectorDatabase(VectorDatabase):
    """Milvus implementation of the vector database interface."""

    def __init__(self, collection_name: str = "MaestroDocs") -> None:
        super().__init__(collection_name)
        # Client connection handle (lazy-created)
        self.client = None
        # Default collection name
        self.collection_name = collection_name
        # Vector dimension for this collection (determined by embedding)
        self.dimension = None
        # Track whether client has been created
        self._client_created = False
        # Store the embedding model used for this collection (string)
        self.embedding_model = None
        # Track collection-level metadata such as embedding, vector size, and chunking
        self._collections_metadata = {}

    def supported_embeddings(self) -> list[str]:
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

    def _ensure_client(self) -> None:
        """Ensure the client is created, handling import-time issues."""
        if not self._client_created:
            self._create_client()
            self._client_created = True

    def _create_client(self) -> None:
        # Temporarily unset MILVUS_URI to prevent pymilvus from auto-connecting during import
        original_milvus_uri = os.environ.pop("MILVUS_URI", None)

        try:
            # Import pymilvus after unsetting the environment variable
            from pymilvus import AsyncMilvusClient

            milvus_uri = original_milvus_uri or "milvus_demo.db"
            milvus_token = os.getenv("MILVUS_TOKEN", None)
            try:
                timeout = int(os.getenv("MILVUS_TIMEOUT", "10"))
            except ValueError:
                timeout = 10

            # For local Milvus Lite, try different URI formats
            try:
                if milvus_token:
                    self.client = AsyncMilvusClient(
                        uri=milvus_uri, token=milvus_token, timeout=timeout
                    )
                else:
                    self.client = AsyncMilvusClient(uri=milvus_uri, timeout=timeout)
            except Exception as e:
                # If the URI format fails, try with file:// prefix
                if not milvus_uri.startswith(("http://", "https://", "file://")):
                    file_uri = f"file://{milvus_uri}"
                    try:
                        if milvus_token:
                            self.client = AsyncMilvusClient(
                                uri=file_uri, token=milvus_token, timeout=timeout
                            )
                        else:
                            self.client = AsyncMilvusClient(
                                uri=file_uri, timeout=timeout
                            )
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

    def _parse_custom_headers(self) -> dict[str, str]:
        """Parse CUSTOM_EMBEDDING_HEADERS environment variable into a dictionary."""
        headers_str = os.getenv("CUSTOM_EMBEDDING_HEADERS")
        if not headers_str:
            return {}

        # Strip leading/trailing quotes that might come from .env files or shell exports
        if (headers_str.startswith('"') and headers_str.endswith('"')) or (
            headers_str.startswith("'") and headers_str.endswith("'")
        ):
            headers_str = headers_str[1:-1]

        try:
            # Try parsing as JSON first
            headers = json.loads(headers_str)
            if isinstance(headers, dict):
                return headers
            # If JSON parsing results in a non-dict (e.g. a string),
            # fall through to key-value parsing.
        except json.JSONDecodeError:
            # Not a valid JSON object, so fall back to key=value parsing
            pass

        headers = {}
        for item in headers_str.split(","):
            # Split only on the first '=' to allow for '=' in the value
            key_value = item.split("=", 1)
            if len(key_value) == 2:
                headers[key_value[0].strip()] = key_value[1].strip()
        return headers

    async def _generate_embedding_async(
        self, text: str, embedding_model: str
    ) -> list[float]:
        """Asynchronously generate embeddings for text using OpenAI's AsyncOpenAI."""
        try:
            from openai import AsyncOpenAI  # type: ignore
        except ImportError as e:
            raise ImportError(
                "openai package with AsyncOpenAI is required. Install/upgrade with: pip install -U openai"
            ) from e

        client_kwargs: dict[str, Any] = {}
        model_to_use = embedding_model
        if embedding_model == "custom_local":
            custom_endpoint_url = os.getenv("CUSTOM_EMBEDDING_URL")
            if not custom_endpoint_url:
                raise ValueError(
                    "CUSTOM_EMBEDDING_URL must be set for 'custom_local' embedding."
                )

            client_kwargs["base_url"] = custom_endpoint_url
            client_kwargs["api_key"] = os.getenv("CUSTOM_EMBEDDING_API_KEY")
            model_to_use = os.getenv("CUSTOM_EMBEDDING_MODEL")
            if not model_to_use:
                raise ValueError(
                    "CUSTOM_EMBEDDING_MODEL must be set for 'custom_local' embedding."
                )

            # Add custom headers if available
            custom_headers = self._parse_custom_headers()
            if custom_headers:
                client_kwargs["default_headers"] = custom_headers
        else:
            # Get OpenAI API key from environment
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY is required for OpenAI embeddings.")
            client_kwargs["api_key"] = api_key

            if model_to_use == "default":
                model_to_use = "text-embedding-ada-002"

        try:
            client = AsyncOpenAI(**client_kwargs)
            resp = await client.embeddings.create(model=model_to_use, input=text)
            return resp.data[0].embedding
        except Exception as e:
            raise RuntimeError(f"Failed to generate embedding asynchronously: {e}")

    def _get_embedding_dimension(self, embedding_model: str) -> int:
        """
        Get the vector dimension for a given embedding model.

        Args:
            embedding_model: Name of the embedding model

        Returns:
            Vector dimension for the model. Raises ValueError if model is unknown or misconfigured.
        """
        if embedding_model == "custom_local":
            vectorsize_str = os.getenv("CUSTOM_EMBEDDING_VECTORSIZE")
            if not vectorsize_str:
                raise ValueError(
                    "CUSTOM_EMBEDDING_VECTORSIZE must be set for 'custom_local' embedding."
                )
            try:
                return int(vectorsize_str)
            except ValueError:
                raise ValueError("CUSTOM_EMBEDDING_VECTORSIZE must be a valid integer.")

        # Map embedding models to their dimensions
        dimension_mapping = {
            "text-embedding-ada-002": 1536,
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
            "default": 1536,
        }

        dimension = dimension_mapping.get(embedding_model)

        if dimension is None:
            raise ValueError(f"Unknown embedding model '{embedding_model}'.")

        return dimension

    async def setup(
        self,
        embedding: str = "default",
        collection_name: str = None,
        chunking_config: dict[str, Any] = None,
    ) -> None:
        """Set up Milvus collection if it doesn't exist."""

        self._ensure_client()
        if embedding == "custom_local":
            custom_url = os.getenv("CUSTOM_EMBEDDING_URL")
            custom_model = os.getenv("CUSTOM_EMBEDDING_MODEL")
            custom_vectorsize = os.getenv("CUSTOM_EMBEDDING_VECTORSIZE")

            if not custom_url:
                raise ValueError(
                    "CUSTOM_EMBEDDING_URL must be set for 'custom_local' embedding."
                )
            if not custom_model:
                raise ValueError(
                    "CUSTOM_EMBEDDING_MODEL must be set for 'custom_local' embedding."
                )
            if not custom_vectorsize:
                raise ValueError(
                    "CUSTOM_EMBEDDING_VECTORSIZE must be set for 'custom_local' embedding."
                )
            try:
                int(custom_vectorsize)
            except ValueError:
                raise ValueError("CUSTOM_EMBEDDING_VECTORSIZE must be a valid integer.")
        if self.client is None:
            warnings.warn("Milvus client is not available. Setup skipped.")
            return

        # Use the specified collection name or fall back to the default
        target_collection = (
            collection_name if collection_name is not None else self.collection_name
        )

        # Store the embedding model
        self.embedding_model = embedding

        # Save chunking config for collection-level metadata
        self._collections_metadata[target_collection] = {
            "embedding": embedding,
            "vector_size": None,  # filled below
            "chunking": chunking_config or {"strategy": "None", "parameters": {}},
        }

        # Determine dimension based on embedding model
        self.dimension = self._get_embedding_dimension(embedding)
        # update stored vector_size
        self._collections_metadata[target_collection]["vector_size"] = self.dimension

        # Create collection if it doesn't exist

        collection_exists = await self.client.has_collection(target_collection)

        if collection_exists:
            try:
                # Use the target collection (not the object's default) when describing
                info = await self.client.describe_collection(target_collection)
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
                # Helpful debug output to indicate which embedding model is configured
                print(f"Using embedding model: {self.embedding_model}")

        if not collection_exists:
            await self.client.create_collection(
                collection_name=target_collection,
                dimension=self.dimension,  # Vector dimension
                primary_field_name="id",
                vector_field_name="vector",
            )
            # Optionally store collection metadata about embedding and chunking
            try:
                # Some Milvus clients support setting collection description/metadata - attempt where available
                if hasattr(self.client, "set_collection_metadata"):
                    meta = {
                        "embedding": self.embedding_model,
                        "vector_size": self.dimension,
                        "chunking": self._collections_metadata.get(
                            target_collection, {}
                        ).get("chunking"),
                    }
                    try:
                        await self.client.set_collection_metadata(
                            target_collection, meta
                        )
                    except Exception:
                        # not critical; ignore if client doesn't support
                        pass
            except Exception:
                pass

    async def write_documents(
        self,
        documents: list[dict[str, Any]],
        embedding: str = "default",
        collection_name: str = None,
    ) -> dict[str, Any]:
        """
        Write documents to Milvus.

        Args:
            documents: List of documents with 'url', 'text', and 'metadata' fields.
                      Documents may also include a 'vector' field for pre-computed embeddings.
            embedding: Embedding strategy to use:
                      - "default": Use pre-computed vector if available, otherwise use text-embedding-ada-002
                      - Specific model name: Use the specified embedding model to generate vectors
            collection_name: Name of the collection to write to (defaults to self.collection_name)
        """
        self._ensure_client()
        if self.client is None:
            warnings.warn("Milvus client is not available. Documents not written.")
            return

        # Use the specified collection name or fall back to the default
        target_collection = (
            collection_name if collection_name is not None else self.collection_name
        )

        # TODO(embedding): Per-write 'embedding' is deprecated; prefer collection-level embedding set in setup().
        #                  In a future release, remove the per-write parameter or make it a no-op.
        # Determine effective embedding model: prefer collection-level embedding if set
        all_supported = self.supported_embeddings()
        if embedding not in all_supported:
            raise ValueError(
                f"Unsupported embedding: {embedding}. Supported: {all_supported}"
            )

        effective_embedding = self.embedding_model or (
            None if embedding == "default" else embedding
        )

        # If collection-level embedding is set and differs from the provided one,
        # ignore the per-write parameter and emit a deprecation warning.
        if self.embedding_model and embedding not in ("default", self.embedding_model):
            warnings.warn(
                "Embedding model should be configured per-collection. The per-write 'embedding' parameter is ignored.",
                stacklevel=2,
            )

        # Chunk documents according to collection chunking config and insert each chunk as a record
        coll_meta = getattr(self, "_collections_metadata", {}).get(
            target_collection, {}
        )
        chunking_conf = coll_meta.get("chunking") if coll_meta else None

        data = []
        stats_per_doc: list[dict[str, Any]] = []
        total_chunks = 0
        build_start = time.perf_counter()
        id_counter = 0

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

        for doc in processed_documents:
            doc_start = time.perf_counter()
            text = doc.get("text", "")
            orig_metadata = dict(doc.get("metadata", {}))

            # Chunk the text
            cfg = ChunkingConfig(
                strategy=(chunking_conf or {}).get("strategy", "None"),
                parameters=(chunking_conf or {}).get("parameters", {}),
            )
            chunks = chunk_text(text, cfg)
            # No automatic re-chunking safety net: if 'None' produces an oversized chunk,
            # we proceed as-is, allowing the backend to surface any size-related errors.

            # Track per-doc
            per_doc_chunk_count = 0
            per_doc_char_count = 0

            for chunk in chunks:
                chunk_text_content = chunk["text"]
                per_doc_chunk_count += 1
                per_doc_char_count += len(chunk_text_content or "")

                # Determine vector for chunk
                if "vector" in doc and doc["vector"] is not None:
                    # Use provided vector if present; validate dimension when known
                    doc_vector = doc["vector"]
                    try:
                        expected_dim = self.dimension or (
                            self._get_embedding_dimension(self.embedding_model)
                            if self.embedding_model
                            else None
                        )
                        if expected_dim is not None and len(doc_vector) != expected_dim:
                            raise ValueError(
                                f"Provided vector dimension {len(doc_vector)} does not match expected {expected_dim}."
                            )
                    except Exception:
                        # If we cannot validate dimension, proceed without blocking
                        pass
                else:
                    # Generate embedding using the effective (collection) model if set; otherwise default
                    model_for_generation = (
                        effective_embedding or "text-embedding-ada-002"
                    )
                    doc_vector = await self._generate_embedding_async(
                        chunk_text_content, model_for_generation
                    )

                if doc_vector is None:
                    raise ValueError("Failed to generate vector for a chunk")

                # Merge metadata and add chunk-specific fields
                new_meta = dict(orig_metadata)
                # Set doc_name from metadata or fall back to URL
                if "doc_name" not in new_meta:
                    new_meta["doc_name"] = doc.get("url", "")
                # omit chunking policy to reduce per-result duplication in search outputs
                # Add ordered chunk-specific metadata (start before end)
                new_meta.update(
                    {
                        "chunk_sequence_number": int(chunk["sequence"]),
                        "total_chunks": int(chunk["total"]),
                        "offset_start": int(chunk["offset_start"]),
                        "offset_end": int(chunk["offset_end"]),
                        "chunk_size": int(chunk["chunk_size"]),
                    }
                )

                data.append(
                    {
                        "id": id_counter,
                        "url": doc.get("url", ""),
                        "text": chunk_text_content,
                        "metadata": json.dumps(new_meta, ensure_ascii=False),
                        "vector": doc_vector,
                    }
                )
                id_counter += 1
                # yield to keep event loop responsive
                await asyncio.sleep(0)
            # end per-doc tracking
            total_chunks += per_doc_chunk_count
            stats_per_doc.append(
                {
                    "name": orig_metadata.get("doc_name")
                    or doc.get("url")
                    or f"doc_{len(stats_per_doc)}",
                    "chunk_count": per_doc_chunk_count,
                    "char_count": per_doc_char_count,
                    "duration_ms": int((time.perf_counter() - doc_start) * 1000),
                }
            )

        insert_duration_ms = 0
        if data:
            insert_start = time.perf_counter()
            try:
                await self.client.insert(target_collection, data)
            except Exception as e:
                # Re-raise the exception to be handled by the caller
                raise e
            insert_duration_ms = int((time.perf_counter() - insert_start) * 1000)

            # Best-effort: ensure Milvus has flushed/loaded the inserted data so
            # that subsequent searches and collection stats reflect the new rows.
            # Different Milvus client wrappers expose different APIs (flush/load/load_collection).
            # Call any available methods safely and ignore failures.
            try:
                # pymilvus-style flush
                if hasattr(self.client, "flush"):
                    try:
                        # Try string format first (more common)
                        await self.client.flush(target_collection)
                    except Exception:
                        # Fall back to list format if string format fails
                        try:
                            await self.client.flush([target_collection])
                        except Exception:
                            pass

                # load collection into queryable memory (client-specific)
                if hasattr(self.client, "load_collection"):
                    try:
                        await self.client.load_collection(target_collection)
                    except Exception:
                        pass
                elif hasattr(self.client, "load"):
                    try:
                        # some wrappers provide a load method
                        await self.client.load(target_collection)
                    except Exception:
                        pass
            except Exception:
                # Don't let flushing/loading interfere with the write path
                pass

        total_duration_ms = int((time.perf_counter() - build_start) * 1000)

        return {
            "backend": "milvus",
            "documents": len(documents),
            "chunks": total_chunks,
            "per_document": stats_per_doc,
            "insert_ms": insert_duration_ms,
            "duration_ms": total_duration_ms,
        }

    async def get_document_chunks(
        self, doc_id: str, collection_name: str = None
    ) -> list[dict[str, Any]]:
        """Retrieve all chunks for a specific document by doc_name."""
        self._ensure_client()
        if self.client is None:
            raise ValueError("Milvus client is not available")

        target_collection = collection_name or self.collection_name
        try:
            # Query for all records with matching doc_name in metadata
            results = await self.client.query(
                target_collection,
                filter=f'metadata["doc_name"] == "{doc_id}"',
                output_fields=["id", "url", "text", "metadata"],
                # Retrieve a reasonable upper bound of chunks to allow reassembly
                limit=10000,
            )

            chunks = []
            for doc in results:
                try:
                    metadata = json.loads(doc.get("metadata", "{}"))
                except Exception:
                    metadata = {}
                chunks.append(
                    {
                        "id": doc.get("id"),
                        "url": doc.get("url", ""),
                        "text": doc.get("text", ""),
                        "metadata": metadata,
                    }
                )

            return chunks
        except Exception as e:
            raise ValueError(f"Failed to retrieve chunks for document '{doc_id}': {e}")

    async def get_document(
        self, doc_name: str, collection_name: str = None
    ) -> dict[str, Any]:
        """Reassemble a document from its chunks by doc_name."""
        # Ensure client is available
        self._ensure_client()
        if self.client is None:
            raise ValueError("Milvus client is not available")

        # Ensure collection exists first
        target_collection = collection_name or self.collection_name
        if not await self.client.has_collection(target_collection):
            raise ValueError(f"Collection '{target_collection}' not found")

        chunks = await self.get_document_chunks(doc_name, collection_name)
        doc = self._reassemble_chunks_into_document(chunks)
        if doc is None:
            raise ValueError(
                f"Document '{doc_name}' not found in collection '{target_collection}'"
            )
        return doc

    async def list_documents(
        self, limit: int = 10, offset: int = 0
    ) -> list[dict[str, Any]]:
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
            results = await self.client.query(
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

    async def count_documents(self) -> int:
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
            stats = await self.client.get_collection_stats(self.collection_name)
            return stats.get("row_count", 0)
        except Exception as e:
            warnings.warn(f"Could not get collection stats: {e}")
            return 0

    async def list_collections(self) -> list[str]:
        """List all collections in Milvus."""
        self._ensure_client()
        if self.client is None:
            warnings.warn("Milvus client is not available. Returning empty list.")
            return []

        try:
            # Get all collections from the client
            collections = await self.client.list_collections()
            return collections
        except Exception as e:
            warnings.warn(f"Could not list collections from Milvus: {e}")
            return []

    async def list_documents_in_collection(
        self, collection_name: str, limit: int = 10, offset: int = 0
    ) -> list[dict[str, Any]]:
        """List documents from a specific collection in Milvus."""
        self._ensure_client()
        if self.client is None:
            warnings.warn("Milvus client is not available. Returning empty list.")
            return []

        try:
            # Check if collection exists first
            if not await self.client.has_collection(collection_name):
                return []

            # Query documents from the specific collection
            results = await self.client.query(
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

    async def count_documents_in_collection(self, collection_name: str) -> int:
        """Get the current count of documents in a specific collection in Milvus."""
        self._ensure_client()
        if self.client is None:
            warnings.warn("Milvus client is not available. Returning 0.")
            return 0

        try:
            # Check if collection exists first
            if not await self.client.has_collection(collection_name):
                return 0

            # Get collection statistics for the specific collection
            stats = await self.client.get_collection_stats(collection_name)
            return stats.get("row_count", 0)
        except Exception as e:
            warnings.warn(
                f"Could not get collection stats for '{collection_name}': {e}"
            )
            return 0

    async def get_collection_info(self, collection_name: str = None) -> dict[str, Any]:
        """Get detailed information about a collection."""
        self._ensure_client()
        if self.client is None:
            warnings.warn("Milvus client is not available. Returning empty info.")
            # Build best-effort embedding details
            emb_name = self.embedding_model or "unknown"
            vec_size = None
            try:
                vec_size = self.dimension or getattr(
                    self, "_collections_metadata", {}
                ).get(collection_name or self.collection_name, {}).get("vector_size")
            except Exception:
                vec_size = None
            provider = (
                "custom"
                if emb_name == "custom_local"
                else (
                    "openai"
                    if emb_name
                    in {
                        "text-embedding-ada-002",
                        "text-embedding-3-small",
                        "text-embedding-3-large",
                        "default",
                    }
                    else "unknown"
                )
            )
            return {
                "name": collection_name or self.collection_name,
                "document_count": 0,
                "db_type": "milvus",
                "embedding": "unknown",
                "chunking": getattr(self, "_collections_metadata", {})
                .get(collection_name or self.collection_name, {})
                .get("chunking"),
                "embedding_details": {
                    "name": emb_name,
                    "vector_size": vec_size,
                    "provider": provider,
                    "source": "collection" if self.embedding_model else "unknown",
                },
                "metadata": {},
            }

        target_collection = collection_name or self.collection_name

        try:
            # Check if collection exists
            if not await self.client.has_collection(target_collection):
                return {
                    "name": target_collection,
                    "document_count": 0,
                    "db_type": "milvus",
                    "embedding": "unknown",
                    "chunking": getattr(self, "_collections_metadata", {})
                    .get(target_collection, {})
                    .get("chunking"),
                    "embedding_details": {
                        "name": self.embedding_model or "unknown",
                        "vector_size": getattr(self, "_collections_metadata", {})
                        .get(target_collection, {})
                        .get("vector_size"),
                        "provider": (
                            "custom"
                            if (self.embedding_model == "custom_local")
                            else (
                                "openai"
                                if (
                                    self.embedding_model
                                    in {
                                        "text-embedding-ada-002",
                                        "text-embedding-3-small",
                                        "text-embedding-3-large",
                                        "default",
                                    }
                                )
                                else "unknown"
                            )
                        ),
                        "source": "collection" if self.embedding_model else "unknown",
                    },
                    "metadata": {"error": "Collection does not exist"},
                }

            # Get collection statistics
            stats = await self.client.get_collection_stats(target_collection)
            try:
                if isinstance(stats, dict):
                    document_count = stats.get("row_count", 0)
                else:
                    # Some clients may return an object; try attribute access
                    document_count = getattr(stats, "row_count", 0)
            except Exception:
                document_count = 0

            # Get collection schema information (dict or object depending on client)
            collection_info = await self.client.describe_collection(target_collection)

            # Use stored embedding model if available, otherwise try to extract from schema
            if self.embedding_model:
                embedding_info = self.embedding_model
            else:
                embedding_info = "unknown"
                # Attempt to parse schema from dict or object
                try:
                    fields = None
                    if isinstance(collection_info, dict):
                        fields = collection_info.get("fields")
                    elif hasattr(collection_info, "fields"):
                        fields = getattr(collection_info, "fields")
                    if fields:
                        for field in fields:
                            # field may be dict or object
                            fname = (
                                field.get("name")
                                if isinstance(field, dict)
                                else getattr(field, "name", None)
                            )
                            if fname == "vector":
                                params = (
                                    field.get("params", {})
                                    if isinstance(field, dict)
                                    else getattr(field, "params", {})
                                )
                                dim_val = (
                                    params.get("dim")
                                    if isinstance(params, dict)
                                    else getattr(params, "dim", "unknown")
                                )
                                embedding_info = f"vector_dim_{dim_val}"
                                break
                except Exception:
                    pass

            # Attempt to include configured chunking metadata if tracked
            chunking_conf = (
                getattr(self, "_collections_metadata", {})
                .get(target_collection, {})
                .get("chunking")
            )

            # Build embedding details
            try:
                dim_from_schema = None
                fields = None
                if isinstance(collection_info, dict):
                    fields = collection_info.get("fields")
                elif hasattr(collection_info, "fields"):
                    fields = getattr(collection_info, "fields")
                if fields:
                    for field in fields:
                        fname = (
                            field.get("name")
                            if isinstance(field, dict)
                            else getattr(field, "name", None)
                        )
                        if fname == "vector":
                            params = (
                                field.get("params", {})
                                if isinstance(field, dict)
                                else getattr(field, "params", {})
                            )
                            dim_from_schema = (
                                params.get("dim")
                                if isinstance(params, dict)
                                else getattr(params, "dim", None)
                            )
                            break
            except Exception:
                dim_from_schema = None

            vec_size = (
                self.dimension
                or getattr(self, "_collections_metadata", {})
                .get(target_collection, {})
                .get("vector_size")
                or dim_from_schema
            )
            provider = (
                "custom"
                if (self.embedding_model == "custom_local")
                else (
                    "openai"
                    if (
                        self.embedding_model
                        in {
                            "text-embedding-ada-002",
                            "text-embedding-3-small",
                            "text-embedding-3-large",
                            "default",
                        }
                    )
                    else "unknown"
                )
            )

            # Extract collection metadata (ID, created_time, description, fields_count)
            try:
                if isinstance(collection_info, dict):
                    collection_id = collection_info.get("id")
                    created_time = collection_info.get("created_time")
                    description = collection_info.get("description")
                    fields_list = collection_info.get("fields") or []
                else:
                    collection_id = getattr(collection_info, "id", None)
                    created_time = getattr(collection_info, "created_time", None)
                    description = getattr(collection_info, "description", None)
                    fields_list = getattr(collection_info, "fields", []) or []
                fields_count = (
                    len(fields_list) if isinstance(fields_list, (list, tuple)) else 0
                )
            except Exception:
                collection_id = None
                created_time = None
                description = None
                fields_count = 0

            # Build optional embedding config for custom_local
            embedding_config = None
            if (self.embedding_model or "") == "custom_local":
                embedding_config = {
                    "url": os.getenv("CUSTOM_EMBEDDING_URL"),
                    "model": os.getenv("CUSTOM_EMBEDDING_MODEL"),
                }

            return {
                "name": target_collection,
                "document_count": document_count,
                "db_type": "milvus",
                "embedding": embedding_info,
                "chunking": chunking_conf,
                "embedding_details": {
                    "name": self.embedding_model or embedding_info,
                    "vector_size": vec_size,
                    "provider": provider,
                    "source": "collection" if self.embedding_model else "schema",
                    **({"config": embedding_config} if embedding_config else {}),
                },
                "metadata": {
                    "collection_id": collection_id,
                    "created_time": created_time,
                    "description": description,
                    "fields_count": fields_count,
                },
            }
        except Exception as e:
            warnings.warn(f"Could not get collection info from Milvus: {e}")
            emb_name = self.embedding_model or "unknown"
            provider = (
                "custom"
                if emb_name == "custom_local"
                else (
                    "openai"
                    if emb_name
                    in {
                        "text-embedding-ada-002",
                        "text-embedding-3-small",
                        "text-embedding-3-large",
                        "default",
                    }
                    else "unknown"
                )
            )
            return {
                "name": target_collection,
                "document_count": 0,
                "db_type": "milvus",
                "embedding": "unknown",
                "chunking": getattr(self, "_collections_metadata", {})
                .get(target_collection, {})
                .get("chunking"),
                "embedding_details": {
                    "name": emb_name,
                    "vector_size": getattr(self, "_collections_metadata", {})
                    .get(target_collection, {})
                    .get("vector_size"),
                    "provider": provider,
                    "source": "collection" if self.embedding_model else "unknown",
                },
                "metadata": {"error": str(e)},
            }

    async def delete_documents(self, document_ids: list[str]) -> None:
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
        try:
            await self.client.delete(self.collection_name, ids=int_ids)
        except Exception as e:
            # Re-raise the exception to be handled by the caller
            raise e

    async def delete_collection(self, collection_name: str = None) -> None:
        """Delete an entire collection from Milvus."""
        self._ensure_client()
        if self.client is None:
            warnings.warn("Milvus client is not available. Collection not deleted.")
            return

        target_collection = collection_name or self.collection_name

        if await self.client.has_collection(target_collection):
            await self.client.drop_collection(target_collection)
            if target_collection == self.collection_name:
                self.collection_name = None

    # TODO: Type needs consideration
    def create_query_agent(self) -> "MilvusVectorDatabase":
        """Create a query agent for Milvus."""
        # Placeholder: Milvus does not have a built-in query agent like Weaviate
        # You would implement your own search logic here
        return self

    async def query(
        self, query: str, limit: int = 5, collection_name: str = None
    ) -> str:
        """
        Query the vector database using Milvus vector similarity search.

        Args:
            query: The query string to search for
            limit: Maximum number of results to consider

        Returns:
            A string response with relevant information from the database
        """
        try:
            # Perform vector similarity search
            documents = await self._search_documents(query, limit, collection_name)

            if not documents:
                return f"No relevant documents found for query: '{query}'"

            # Format the response
            response_parts = [f"Query: {query}\n"]
            response_parts.append(f"Found {len(documents)} relevant documents:\n")

            for i, doc in enumerate(documents, 1):
                url = doc.get("url", "No URL")
                text = doc.get("text", "No text content")
                score = doc.get("score", "N/A")

                # Truncate text if too long
                if len(text) > 500:
                    text = text[:500] + "..."

                response_parts.append(f"\n{i}. Document (Score: {score}):")
                response_parts.append(f"   URL: {url}")
                response_parts.append(f"   Content: {text}")

            return "\n".join(response_parts)

        except Exception as e:
            warnings.warn(f"Failed to query Milvus: {e}")
            return f"Error querying database: {str(e)}"

    async def _search_documents(
        self, query: str, limit: int = 5, collection_name: str = None
    ) -> list[dict[str, Any]]:
        """
        Search for documents using vector similarity search.

        Args:
            query: The search query text
            limit: Maximum number of results to return
            collection_name: Optional collection name to search in (defaults to self.collection_name)

        Returns:
            List of documents sorted by relevance
        """
        try:
            self._ensure_client()
            if self.client is None:
                warnings.warn("Milvus client is not available. Returning empty list.")
                return []

            # Generate embedding for the query without blocking the event loop
            query_vector = await self._generate_embedding_async(
                query, self.embedding_model or "default"
            )

            # Perform vector similarity search. Different client wrappers use
            # slightly different parameter names/signatures. Inspect the
            # available signature and try compatible call patterns. Build a
            # search_params object and attempt a safe call sequence.
            import inspect

            target_collection = collection_name or self.collection_name
            search_params = {"metric_type": "COSINE", "params": {"nprobe": 10}}

            results = None
            try:
                # Inspect client's signature and build matching kwargs to avoid
                # passing duplicated parameters that some wrappers reject.
                sig = inspect.signature(self.client.search)
                params = sig.parameters.keys()
                kwargs = {}
                if "data" in params:
                    kwargs["data"] = [query_vector]
                if "anns_field" in params:
                    kwargs["anns_field"] = "vector"
                if "param" in params:
                    kwargs["param"] = search_params
                elif "params" in params:
                    kwargs["params"] = search_params
                elif "search_params" in params:
                    kwargs["search_params"] = search_params

                if "limit" in params:
                    kwargs["limit"] = limit
                if "output_fields" in params:
                    kwargs["output_fields"] = ["id", "url", "text", "metadata"]

                results = await self.client.search(target_collection, **kwargs)
            except Exception as e:
                # If signature introspection or the call itself fails, try a
                # positional fallback as a last resort. Do not re-raise to
                # keep the server running; we'll fall back to keyword search.
                try:
                    results = await self.client.search(
                        target_collection,
                        [query_vector],
                        "vector",
                        search_params,
                        limit,
                    )
                except Exception:
                    logger = logging.getLogger(__name__)
                    try:
                        logger.warning(
                            f"Milvus client.search raised unexpected error: {e}"
                        )
                    except Exception:
                        pass
                    results = None

            # Log a small sample of the raw results for debugging purposes
            try:
                logger = logging.getLogger(__name__)
                sample = None
                if isinstance(results, list):
                    # If nested list-of-lists, grab first inner list sample
                    if results and isinstance(results[0], list):
                        sample = results[0][:3]
                    else:
                        sample = results[:3]
                else:
                    sample = repr(results)
                logger.info(
                    "Milvus raw search results sample (type=%s): %s",
                    type(results),
                    repr(sample)[:2000],
                )
            except Exception:
                # Do not fail search due to logging
                pass

            # Normalize results: some wrappers return a flat list of hit dicts,
            # others return a list-of-lists (one list per query vector). Handle
            # both shapes and populate explicit diagnostic fields per hit.
            documents = []

            # Helper to process an individual hit object (different shapes)
            def _process_hit(hit_obj: dict[str, Any]) -> dict[str, Any]:
                # If wrapper returns Hit objects with .entity and .score
                try:
                    raw_score = None
                    raw_distance = None
                    raw_similarity = None
                    if hasattr(hit_obj, "entity"):
                        entity = hit_obj.entity
                        try:
                            metadata = json.loads(entity.get("metadata", "{}"))
                        except Exception:
                            metadata = {}
                        doc_id = entity.get("id")
                        url = entity.get("url", "")
                        text = entity.get("text", "")
                        # Capture potential raw fields
                        try:
                            if getattr(hit_obj, "score", None) is not None:
                                raw_score = getattr(hit_obj, "score")
                            if getattr(hit_obj, "distance", None) is not None:
                                raw_distance = getattr(hit_obj, "distance")
                            if isinstance(entity, dict):
                                if entity.get("score") is not None:
                                    raw_score = entity.get("score")
                                if entity.get("distance") is not None:
                                    raw_distance = entity.get("distance")
                                if entity.get("similarity") is not None:
                                    raw_similarity = entity.get("similarity")
                        except Exception:
                            pass
                    elif isinstance(hit_obj, dict):
                        # Flat-dict return shape from some wrappers
                        try:
                            metadata = json.loads(hit_obj.get("metadata", "{}"))
                        except Exception:
                            metadata = (
                                hit_obj.get("metadata")
                                if hit_obj.get("metadata")
                                else {}
                            )
                        doc_id = hit_obj.get("id")
                        url = hit_obj.get("url", "")
                        text = hit_obj.get("text", "")
                        # Raw fields under different keys
                        raw_score = hit_obj.get("score")
                        raw_distance = hit_obj.get("distance")
                        raw_similarity = hit_obj.get("similarity")
                    else:
                        # Unknown shape: attempt attribute access defensively
                        metadata = {}
                        doc_id = getattr(hit_obj, "id", None)
                        url = getattr(hit_obj, "url", "")
                        text = getattr(hit_obj, "text", "")
                        if getattr(hit_obj, "score", None) is not None:
                            raw_score = getattr(hit_obj, "score")
                        if getattr(hit_obj, "distance", None) is not None:
                            raw_distance = getattr(hit_obj, "distance")

                    doc = {
                        "id": doc_id,
                        "url": url,
                        "text": text,
                        # Remove verbose chunking policy from per-result metadata
                        "metadata": (
                            {
                                k: v
                                for k, v in (metadata or {}).items()
                                if k != "chunking"
                            }
                            if isinstance(metadata, dict)
                            else metadata
                        ),
                        # Explicit diagnostic marker so clients can tell vector vs keyword
                        "_search_mode": "vector",
                        "_metric": "cosine",
                        "_query_vector_len": len(query_vector)
                        if query_vector is not None
                        else None,
                    }

                    # Do not include raw_* values in output; keep normalized view only

                    # Compute normalized similarity [0,1] and distance (assume cosine)
                    similarity = None
                    distance = None
                    try:
                        if raw_distance is not None:
                            distance = float(raw_distance)
                            similarity = max(0.0, min(1.0, 1.0 - distance))
                        elif raw_similarity is not None:
                            s = float(raw_similarity)
                            similarity = max(0.0, min(1.0, s))
                            distance = 1.0 - similarity
                        elif raw_score is not None:
                            s = float(raw_score)
                            if 0.0 <= s <= 1.000001:
                                similarity = max(0.0, min(1.0, s))
                                distance = 1.0 - similarity
                            elif 1.0 < s <= 2.000001:
                                distance = s
                                similarity = max(0.0, min(1.0, 1.0 - s))
                    except Exception:
                        pass

                    if distance is not None:
                        doc["distance"] = distance
                    if similarity is not None:
                        doc["similarity"] = similarity

                    return doc
                except Exception:
                    return None

            # Flatten nested results or use flat list
            if results is None:
                return []

            # If results is a list-of-lists (per query vector), iterate nested
            if isinstance(results, list) and results and isinstance(results[0], list):
                for hits in results:
                    for hit in hits:
                        doc = _process_hit(hit)
                        if doc:
                            documents.append(doc)
            elif isinstance(results, list):
                # Flat list of hit dicts/objects
                for hit in results:
                    doc = _process_hit(hit)
                    if doc:
                        documents.append(doc)
            else:
                # Unexpected shape: try to iterate
                try:
                    for hit in results:
                        doc = _process_hit(hit)
                        if doc:
                            documents.append(doc)
                except Exception:
                    # Give up and return empty
                    return []

            # Add explicit rank 1..N and normalize metadata keys
            for i, d in enumerate(documents, start=1):
                try:
                    d["rank"] = i
                    # Normalize metadata: remove chunking and map old key to new
                    if isinstance(d.get("metadata"), dict):
                        md = d["metadata"]
                        if "chunking" in md:
                            md.pop("chunking", None)
                except Exception:
                    pass

            return documents

        except Exception as e:
            warnings.warn(f"Failed to perform vector search for query '{query}': {e}")
            # Fallback to simple keyword matching if vector search fails
            return await self._fallback_keyword_search(query, limit)

    async def search(
        self, query: str, limit: int = 5, collection_name: str = None
    ) -> list[dict[str, Any]]:
        """
        Public search method required by the abstract base class. Delegates
        to the internal _search_documents implementation.
        """
        return await self._search_documents(query, limit, collection_name)

    async def _fallback_keyword_search(
        self, query: str, limit: int = 5
    ) -> list[dict[str, Any]]:
        """
        Fallback to simple keyword matching if vector search fails.

        Args:
            query: The search query text
            limit: Maximum number of results to return

        Returns:
            List of documents sorted by relevance
        """
        try:
            # Get all documents and perform keyword matching
            documents = await self.list_documents(limit=100, offset=0)

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
        """Clean up Milvus client."""
        if self.client is not None:
            if self.collection_name:
                if await self.client.has_collection(self.collection_name):
                    try:
                        await self.client.drop_collection(self.collection_name)
                    except Exception:
                        pass
            # Explicitly close the async client to release gRPC resources
            try:
                await self.client.close()
            except Exception:
                pass
        self.client = None

    @property
    def db_type(self) -> str:
        return "milvus"
