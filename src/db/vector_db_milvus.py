# SPDX-License-Identifier: Apache 2.0
# Copyright (c) 2025 IBM

import asyncio
import json
import logging
import os
import time
import warnings
from typing import Any

from src.chunking import ChunkingConfig, chunk_text
from src.db.document_id import generate_document_id

try:
    from pymilvus import DataType
except ImportError:
    DataType = None

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
        # Write serialization lock for Milvus Lite environments
        self._write_lock = asyncio.Lock()
        # Determine if we need write serialization based on environment
        self._serialize_writes = self._should_serialize_writes()

    def _should_serialize_writes(self) -> bool:
        """
        Determine if write operations should be serialized.

        Write serialization prevents concurrent write issues in Milvus.
        Defaults to enabled for safety.

        Returns:
            True if writes should be serialized, False otherwise
        """
        # Check for explicit environment variable override
        serialize_env = os.getenv("MILVUS_SERIALIZE_WRITES", "true").lower()

        if serialize_env == "true" or serialize_env == "1":
            logger.debug("Write serialization enabled")
            return True
        elif serialize_env == "false" or serialize_env == "0":
            logger.info("Write serialization DISABLED by environment variable")
            return False

        # Default to enabled for safety
        logger.debug("Write serialization enabled (default)")
        return True

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
    ) -> None:
        """
        Initialize the Milvus database connection.

        This method only sets up the database client connection.
        Collections must be created explicitly using create_collection().

        Args:
            embedding: Default embedding model to use (stored for reference)
        """
        self._ensure_client()

        # Validate custom_local embedding configuration if specified
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

        # Store the default embedding model for reference
        self.embedding_model = embedding

    async def create_collection(
        self,
        collection_name: str,
        embedding: str = "default",
        chunking_config: dict[str, Any] | None = None,
    ) -> None:
        """
        Create a new collection in Milvus.

        Args:
            collection_name: Name of the collection to create
            embedding: Embedding model to use for the collection
            chunking_config: Configuration for the chunking strategy
        """
        self._ensure_client()

        if self.client is None:
            raise RuntimeError("Milvus client is not available")

        # Validate custom_local embedding configuration if specified
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

        # Save chunking config for collection-level metadata
        # Phase 8.5: Default to Sentence chunking (512 chars, 0 overlap) instead of None
        default_chunking = {
            "strategy": "Sentence",
            "parameters": {"chunk_size": 512, "overlap": 0},
        }
        self._collections_metadata[collection_name] = {
            "embedding": embedding,
            "vector_size": None,  # filled below
            "chunking": chunking_config or default_chunking,
        }

        # Determine dimension based on embedding model
        dimension = self._get_embedding_dimension(embedding)
        # update stored vector_size
        self._collections_metadata[collection_name]["vector_size"] = dimension

        # Check if collection already exists
        collection_exists = await self.client.has_collection(collection_name)

        if collection_exists:
            try:
                info = await self.client.describe_collection(collection_name)
                for field in info.get("fields", []):
                    if field.get("name") == "vector":
                        existing_dim = field.get("params", {}).get("dim")
                        if existing_dim != dimension:
                            raise ValueError(
                                f"Collection '{collection_name}' already exists with dimension {existing_dim}, "
                                f"but requested dimension is {dimension}"
                            )
                # Collection exists with correct dimension
                return
            except Exception as e:
                if "already exists" not in str(e).lower():
                    raise

        # Create schema with auto-increment ID
        if DataType is None:
            raise RuntimeError(
                "DataType not available - pymilvus not installed properly"
            )

        schema = self.client.create_schema()

        # Primary key field with auto-increment
        schema.add_field(
            field_name="id", datatype=DataType.INT64, is_primary=True, auto_id=True
        )

        # Vector field
        schema.add_field(
            field_name="vector", datatype=DataType.FLOAT_VECTOR, dim=dimension
        )

        # Text field
        schema.add_field(field_name="text", datatype=DataType.VARCHAR, max_length=65535)

        # URL field
        schema.add_field(field_name="url", datatype=DataType.VARCHAR, max_length=512)

        # Metadata field as JSON
        schema.add_field(field_name="metadata", datatype=DataType.JSON)

        # Create collection with schema
        await self.client.create_collection(
            collection_name=collection_name, schema=schema
        )

        # Create index on vector field (required before loading)
        index_params = self.client.prepare_index_params()
        index_params.add_index(
            field_name="vector",
            index_type="FLAT",  # Simple flat index for small datasets
            metric_type="COSINE",
        )
        await self.client.create_index(
            collection_name=collection_name, index_params=index_params
        )

        # Load collection into memory (required for querying)
        await self.client.load_collection(collection_name=collection_name)

        # Optionally store collection metadata about embedding and chunking
        try:
            if hasattr(self.client, "set_collection_metadata"):
                meta = {
                    "embedding": embedding,
                    "vector_size": dimension,
                    "chunking": self._collections_metadata.get(collection_name, {}).get(
                        "chunking"
                    ),
                }
                try:
                    await self.client.set_collection_metadata(collection_name, meta)
                except Exception:
                    pass
        except Exception:
            pass

    async def write_documents(
        self,
        documents: list[dict[str, Any]],
        collection_name: str | None = None,
    ) -> dict[str, Any]:
        """
        Write documents to Milvus.

        Args:
            documents: List of documents with 'url', 'text', and 'metadata' fields.
                      Documents may also include a 'vector' field for pre-computed embeddings.
            collection_name: Name of the collection to write to (defaults to self.collection_name)

        Note:
            Embedding model is configured at collection creation time via setup().
            Each chunk will automatically include embedding_model metadata.
        """
        self._ensure_client()
        if self.client is None:
            warnings.warn("Milvus client is not available. Documents not written.")
            return

        # Use the specified collection name or fall back to the default
        target_collection = (
            collection_name if collection_name is not None else self.collection_name
        )

        # Use collection-level embedding model (set during setup)
        effective_embedding = self.embedding_model

        # Chunk documents according to collection chunking config and insert each chunk as a record
        coll_meta = getattr(self, "_collections_metadata", {}).get(
            target_collection, {}
        )
        chunking_conf = coll_meta.get("chunking") if coll_meta else None

        # Apply default chunking if no config is found (e.g., after server restart)
        # Phase 8.5: Default to Sentence chunking (512 chars, 0 overlap) instead of None
        if chunking_conf is None:
            chunking_conf = {
                "strategy": "Sentence",
                "parameters": {"chunk_size": 512, "overlap": 0},
            }
            logger.info(
                f"No chunking config found for '{target_collection}', using default: Sentence(512, 0)"
            )

        data = []
        stats_per_doc: list[dict[str, Any]] = []
        total_chunks = 0
        build_start = time.perf_counter()
        document_ids: list[str] = []  # Track document IDs for return value

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
            # Generate document_id for this document
            text = doc.get("text", "")
            url = doc.get("url")
            document_id = generate_document_id(text, url)
            document_ids.append(document_id)

            doc_start = time.perf_counter()
            orig_metadata = dict(doc.get("metadata", {}))

            # Add document_id to metadata
            orig_metadata["document_id"] = document_id

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
                        # Remove "id" field to let Milvus auto-generate unique IDs
                        "url": doc.get("url", ""),
                        "text": chunk_text_content,
                        "metadata": new_meta,  # Pass as dict for JSON field
                        "vector": doc_vector,
                    }
                )
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
            # Wrap insert/flush/verify in lock if serialization is enabled
            async def perform_write() -> None:
                nonlocal insert_duration_ms
                insert_start = time.perf_counter()

                expected_count = len(data)
                # Track document_ids for verification (from metadata)
                written_doc_ids = document_ids.copy()

                try:
                    # Step 1: Insert data (Milvus will auto-generate IDs)
                    await self.client.insert(target_collection, data)
                    insert_duration_ms = int(
                        (time.perf_counter() - insert_start) * 1000
                    )

                    # Step 2: Flush
                    logger.info(f"Issuing flush command for: {target_collection}")
                    if hasattr(self.client, "flush"):
                        try:
                            await self.client.flush(target_collection)
                        except Exception:
                            try:
                                await self.client.flush([target_collection])
                            except Exception:
                                pass

                    # Step 3: Ground-truth verification - query by document_ids
                    logger.info(
                        f"Verifying write of {expected_count} chunks for {len(written_doc_ids)} documents..."
                    )
                    max_wait_time = 30.0
                    poll_interval = 0.5
                    start_time = time.time()
                    verified = False

                    while time.time() - start_time < max_wait_time:
                        # Reload collection to see new segments
                        if hasattr(self.client, "load_collection"):
                            try:
                                await self.client.load_collection(target_collection)
                            except Exception:
                                pass

                        # Query by document_ids in metadata to verify
                        try:
                            # Build filter for all document_ids we just wrote
                            doc_id_filters = " or ".join(
                                [
                                    f'metadata["document_id"] == "{doc_id}"'
                                    for doc_id in written_doc_ids
                                ]
                            )

                            results = await self.client.query(
                                target_collection,
                                filter=doc_id_filters,
                                output_fields=["id", "metadata"],
                                limit=expected_count + 100,  # Buffer
                            )

                            if len(results) >= expected_count:
                                logger.info(
                                    f"VERIFIED: All {expected_count} chunks are persisted and queryable"
                                )
                                verified = True
                                break
                            else:
                                logger.debug(
                                    f"Verification: Found {len(results)} of {expected_count} chunks, waiting..."
                                )
                        except Exception as e:
                            logger.debug(f"Verification query failed (will retry): {e}")

                        await asyncio.sleep(poll_interval)

                    if not verified:
                        logger.error(
                            f"Write verification FAILED after {max_wait_time}s. Data may not be persisted!"
                        )
                        raise Exception(
                            f"Milvus write verification failed for {target_collection}: {expected_count} chunks not queryable"
                        )

                except Exception as e:
                    logger.error(f"Write operation failed: {e}")
                    raise e

            # Execute write with or without lock based on configuration
            if self._serialize_writes:
                logger.debug("Acquiring write lock (Milvus Lite mode)")
                async with self._write_lock:
                    await perform_write()
            else:
                await perform_write()

            # Legacy fallback: Also reload collection after write completes
            try:
                logger.info(f"Loading collection: {target_collection}")
                if hasattr(self.client, "load_collection"):
                    try:
                        await self.client.load_collection(target_collection)
                        logger.info("Collection loaded. Data is now queryable.")
                    except Exception as e:
                        logger.warning(f"Failed to load collection: {e}")
                elif hasattr(self.client, "load"):
                    try:
                        # some wrappers provide a load method
                        await self.client.load(target_collection)
                        logger.info("Collection loaded. Data is now queryable.")
                    except Exception as e:
                        logger.warning(f"Failed to load collection: {e}")
            except Exception as e:
                # Don't let flushing/loading interfere with the write path
                logger.warning(f"Error during flush/load sequence: {e}")

        total_duration_ms = int((time.perf_counter() - build_start) * 1000)

        return {
            "backend": "milvus",
            "documents": len(documents),
            "chunks": total_chunks,
            "per_document": stats_per_doc,
            "insert_ms": insert_duration_ms,
            "duration_ms": total_duration_ms,
            "document_ids": document_ids,  # NEW: Return list of document IDs
        }

    async def get_document_chunks(
        self, document_id: str, collection_name: str | None = None
    ) -> list[dict[str, Any]]:
        """Retrieve all chunks for a specific document by document_id.

        Args:
            document_id: The document ID (from metadata) to retrieve chunks for
            collection_name: Optional collection name, uses default if not provided

        Returns:
            List of chunk dictionaries with id, url, text, and metadata
        """
        self._ensure_client()
        if self.client is None:
            raise ValueError("Milvus client is not available")

        target_collection = collection_name or self.collection_name

        # Ensure collection is loaded into memory before querying
        try:
            if hasattr(self.client, "load_collection"):
                await self.client.load_collection(target_collection)
        except Exception:
            pass  # Continue even if load fails

        try:
            # Query for all records with matching document_id in metadata
            # Note: metadata is stored as JSON, so we use JSON path for filtering
            results = await self.client.query(
                target_collection,
                filter=f'metadata["document_id"] == "{document_id}"',
                output_fields=["id", "url", "text", "metadata"],
                # Retrieve a reasonable upper bound of chunks to allow reassembly
                limit=10000,
            )

            chunks = []
            for doc in results:
                # Metadata is already a dict with JSON field type
                metadata = doc.get("metadata", {})
                if not isinstance(metadata, dict):
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
            raise ValueError(
                f"Failed to retrieve chunks for document '{document_id}': {e}"
            )

    async def get_document(
        self, document_id: str, collection_name: str | None = None
    ) -> dict[str, Any]:
        """Reassemble a document from its chunks by document_id.

        Args:
            document_id: The document ID (from metadata) to retrieve
            collection_name: Optional collection name, uses default if not provided

        Returns:
            Dictionary with reassembled document including text, url, and metadata
        """
        # Ensure client is available
        self._ensure_client()
        if self.client is None:
            raise ValueError("Milvus client is not available")

        # Ensure collection exists first
        target_collection = collection_name or self.collection_name
        if not await self.client.has_collection(target_collection):
            raise ValueError(f"Collection '{target_collection}' not found")

        chunks = await self.get_document_chunks(document_id, collection_name)
        doc = self._reassemble_chunks_into_document(chunks)
        if doc is None:
            raise ValueError(
                f"Document with ID '{document_id}' not found in collection '{target_collection}'"
            )
        return doc

    async def list_documents(
        self,
        limit: int = 10,
        offset: int = 0,
        name_filter: str | None = None,
        url_filter: str | None = None,
        metadata_filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """List unique documents from Milvus (one entry per document, not per chunk).

        Returns document-level information including document_id, URL, name, and chunk count.
        Does not return full text content.

        Args:
            limit: Maximum number of documents to return
            offset: Number of documents to skip (for pagination)
            name_filter: Optional substring to filter by document name (case-insensitive)
            url_filter: Optional substring to filter by URL (case-insensitive)
            metadata_filters: Optional dictionary of metadata field filters. Only documents matching ALL filters are returned.
        """
        self._ensure_client()
        if self.client is None:
            warnings.warn("Milvus client is not available. Returning empty list.")
            return []

        # Check if collection name is set
        if self.collection_name is None:
            warnings.warn("No collection name set. Returning empty list.")
            return []

        # Ensure collection is loaded into memory before querying
        try:
            if hasattr(self.client, "load_collection"):
                await self.client.load_collection(self.collection_name)
        except Exception:
            pass  # Continue even if load fails

        try:
            # Query all chunks to aggregate by document_id
            # Use primary key filter for reliable "get all" query
            # With auto-increment IDs (positive 64-bit integers), id > 0 matches all records
            # This uses the PK index and is much more reliable than full VARCHAR scans
            results = await self.client.query(
                self.collection_name,
                filter="id > 0",  # PK-indexed filter - reliable and efficient
                output_fields=["url", "metadata"],
                limit=16384,  # High limit to get all chunks
            )
            logger.info(f"Number of chunks retrieved: {len(results)}")

            # DEBUG: Log first few chunks
            for i, chunk in enumerate(results[:5]):
                metadata_str = str(chunk.get("metadata", "N/A"))[:200]
                logger.info(
                    f"DEBUG Chunk {i}: url={chunk.get('url', 'N/A')}, metadata={metadata_str}"
                )

            # Group chunks by document_id and store full metadata
            docs_by_id: dict[str, dict[str, Any]] = {}
            for chunk in results:
                # Metadata is already a dict with JSON field type
                metadata = chunk.get("metadata", {})
                if not isinstance(metadata, dict):
                    metadata = {}
                doc_id = metadata.get("document_id")
                if not doc_id:
                    logger.warning(
                        f"DEBUG: Chunk without document_id: {chunk.get('url', 'N/A')}"
                    )
                    continue  # Skip chunks without document_id

                if doc_id not in docs_by_id:
                    docs_by_id[doc_id] = {
                        "document_id": doc_id,
                        "url": chunk.get("url", ""),
                        "name": metadata.get("doc_name", ""),
                        "chunks": 0,
                        "metadata": metadata,  # Store full metadata for filtering
                    }
                docs_by_id[doc_id]["chunks"] += 1

            # Convert to list
            all_docs = list(docs_by_id.values())
            logger.info(
                f"DEBUG: Found {len(all_docs)} unique documents before filtering"
            )
            for doc in all_docs[:10]:
                logger.info(
                    f"DEBUG Doc: {doc['document_id']}, chunks={doc['chunks']}, url={doc['url']}"
                )

            # Apply filters if provided
            if name_filter:
                name_lower = name_filter.lower()
                all_docs = [d for d in all_docs if name_lower in d["name"].lower()]

            if url_filter:
                url_lower = url_filter.lower()
                all_docs = [d for d in all_docs if url_lower in d["url"].lower()]

            # Apply metadata filters if provided
            if metadata_filters:
                filtered_docs = []
                for doc in all_docs:
                    doc_metadata = doc.get("metadata", {})
                    # Check if all filter conditions match
                    matches_all = all(
                        doc_metadata.get(key) == value
                        for key, value in metadata_filters.items()
                    )
                    if matches_all:
                        filtered_docs.append(doc)
                all_docs = filtered_docs

            # Remove metadata from final output (it was only needed for filtering)
            for doc in all_docs:
                doc.pop("metadata", None)

            # Apply pagination
            start_idx = offset
            end_idx = offset + limit
            return all_docs[start_idx:end_idx]

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
            # Check if event loop is running before async operation
            import asyncio

            try:
                asyncio.get_running_loop()
            except RuntimeError:
                # Event loop is closed, return empty list gracefully
                return []

            # Get all collections from the client
            collections = await self.client.list_collections()
            return collections
        except Exception as e:
            # Suppress warning if it's just an event loop closure during cleanup
            if "Event loop is closed" not in str(e):
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
                # Metadata is already a dict with JSON field type
                metadata = doc.get("metadata", {})
                if not isinstance(metadata, dict):
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

    async def get_collection_info(
        self, collection_name: str | None = None
    ) -> dict[str, Any]:
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
        """Delete documents from Milvus by their document_ids.

        Args:
            document_ids: List of document IDs (from metadata) to delete.
                         All chunks with matching document_id will be deleted.
        """
        self._ensure_client()
        if self.client is None:
            warnings.warn("Milvus client is not available. Documents not deleted.")
            return

        # Delete all chunks for each document_id
        # Use two-step approach: query for IDs first, then delete by ID list
        # This is necessary because delete() doesn't support LIKE filters efficiently
        for doc_id in document_ids:
            try:
                # Step 1: Query for the primary key IDs of chunks to delete
                query_expr = f'metadata["document_id"] == "{doc_id}"'
                results = await self.client.query(
                    collection_name=self.collection_name,
                    filter=query_expr,
                    output_fields=["id"],  # Only fetch the primary key
                    limit=16384,  # Maximum limit
                )

                if not results:
                    continue  # No chunks found for this document_id

                # Step 2: Extract the list of IDs and delete by ID
                ids_to_delete = [item["id"] for item in results]
                delete_expr = f"id in {ids_to_delete}"

                await self.client.delete(
                    collection_name=self.collection_name, filter=delete_expr
                )
            except Exception as e:
                warnings.warn(f"Failed to delete document {doc_id}: {e}")

    async def delete_collection(self, collection_name: str | None = None) -> None:
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

    async def _search_documents(
        self,
        query: str,
        limit: int = 5,
        collection_name: str | None = None,
        min_score: float | None = None,
        metadata_filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Search for documents using vector similarity search.

        Args:
            query: The search query text
            limit: Maximum number of results to return
            collection_name: Optional collection name to search in (defaults to self.collection_name)
            min_score: Minimum similarity score threshold (0-1). Results below this are filtered out.
            metadata_filters: Dictionary of metadata field filters. Only results matching all filters are returned.

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
                        # Metadata is already a dict with JSON field type
                        metadata = entity.get("metadata", {})
                        if not isinstance(metadata, dict):
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
                        # Metadata is already a dict with JSON field type
                        metadata = hit_obj.get("metadata", {})
                        if not isinstance(metadata, dict):
                            metadata = {}
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

                    # Remove verbose chunking policy from per-result metadata
                    clean_metadata = (
                        {k: v for k, v in (metadata or {}).items() if k != "chunking"}
                        if isinstance(metadata, dict)
                        else metadata
                    )

                    doc = {
                        "id": doc_id,
                        "text": text,
                        "metadata": clean_metadata,
                        # Explicit diagnostic marker so clients can tell vector vs keyword
                        "_search_mode": "vector",
                        "_metric": "cosine",
                        "_query_vector_len": len(query_vector)
                        if query_vector is not None
                        else None,
                    }

                    # Extract document_id from metadata (added during write)
                    if isinstance(clean_metadata, dict):
                        document_id = clean_metadata.get("document_id")
                        if document_id:
                            doc["document_id"] = document_id

                    # Phase 5: Add top-level URL and source citation
                    if url:
                        doc["url"] = url
                        doc_name = (
                            clean_metadata.get("doc_name", "Unknown")
                            if isinstance(clean_metadata, dict)
                            else "Unknown"
                        )
                        doc["source_citation"] = f"Source: {doc_name} ({url})"
                    elif isinstance(clean_metadata, dict) and clean_metadata.get(
                        "doc_name"
                    ):
                        doc["source_citation"] = (
                            f"Source: {clean_metadata.get('doc_name')}"
                        )

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
                        # Use similarity as the canonical score field
                        doc["score"] = similarity

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

            # Phase 4: Apply min_score filter
            if min_score is not None:
                documents = [
                    d
                    for d in documents
                    if d.get("score", 0) >= min_score
                    or d.get("similarity", 0) >= min_score
                ]

            # Phase 4: Apply metadata filters
            if metadata_filters:
                filtered_docs = []
                for d in documents:
                    doc_metadata = d.get("metadata", {})
                    if isinstance(doc_metadata, dict):
                        # Check if all filter conditions match
                        if all(
                            doc_metadata.get(k) == v
                            for k, v in metadata_filters.items()
                        ):
                            filtered_docs.append(d)
                documents = filtered_docs

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
        self,
        query: str,
        limit: int = 5,
        collection_name: str | None = None,
        min_score: float | None = None,
        metadata_filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Public search method required by the abstract base class. Delegates
        to the internal _search_documents implementation.

        Args:
            query: The search query text
            limit: Maximum number of results to return
            collection_name: Optional collection name to search in
            min_score: Minimum similarity score threshold (0-1)
            metadata_filters: Dictionary of metadata field filters

        Returns:
            List of documents sorted by relevance
        """
        return await self._search_documents(
            query, limit, collection_name, min_score, metadata_filters
        )

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
            # Use high limit to ensure we get all documents for keyword search
            documents = await self.list_documents(limit=4096, offset=0)

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
