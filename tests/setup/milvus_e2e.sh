#!/bin/bash
# Setup script for Milvus E2E testing

echo "🚀 Setting up Milvus for E2E testing..."

# Use docker directly (works with Docker Desktop, Colima, Podman with docker alias)
if ! docker info >/dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    echo "   For Colima users: colima start"
    exit 1
fi
echo "📦 Using Docker for container management"

echo "📦 Starting Milvus container (ARM64 compatible)..."

# Stop existing container if running
docker stop milvus-simple 2>/dev/null || true
docker rm milvus-simple 2>/dev/null || true

# Start Milvus with ARM64 compatible image and proper standalone configuration
docker run -d \
  --name milvus-simple \
  -p 19530:19530 \
  -p 9091:9091 \
  -v milvus-data:/var/lib/milvus \
  -e ETCD_USE_EMBED=true \
  -e ETCD_DATA_DIR=/var/lib/milvus/etcd \
  -e COMMON_STORAGETYPE=local \
  -e DEPLOY_MODE=STANDALONE \
  milvusdb/milvus:v2.6.1 \
  /milvus/bin/milvus run standalone

echo "⏳ Waiting for Milvus to start..."
sleep 15

# Check if Milvus is responding
echo "🔍 Testing Milvus connectivity..."
for i in {1..30}; do
    if docker exec milvus-simple milvus --help >/dev/null 2>&1; then
        echo "✅ Milvus container is responsive!"
        break
    fi
    echo "   ... waiting for container (${i}/30)"
    sleep 2
done

# Additional check - test the port
sleep 5
echo "🔍 Testing port connectivity..."
for i in {1..15}; do
    if nc -z localhost 19530 2>/dev/null; then
        echo "✅ Milvus port 19530 is accessible!"
        break
    fi
    echo "   ... waiting for port (${i}/15)"
    sleep 2
done

# Verify both services
echo ""
echo "🔍 Final Service Status:"
echo "Milvus container:"
if docker ps | grep milvus-simple | grep -q Up; then
    echo "  ✅ Container running"
    echo "     Image: milvusdb/milvus:v2.6.1 (ARM64 compatible)"
    echo "     Ports: 19530:19530, 9091:9091"
else
    echo "  ❌ Container not running"
fi

echo "Milvus port (19530):"
if nc -z localhost 19530 2>/dev/null; then
    echo "  ✅ Accessible"
else
    echo "  ❌ Not accessible"
fi

echo "Embedding service (port 11434):"
if nc -z localhost 11434 2>/dev/null; then
    echo "  ✅ Running (Ollama)"
else
    echo "  ❌ Not running (start with: ollama serve)"
    echo "     Required for E2E tests. Install: https://ollama.ai"
    echo "     Then run: ollama pull nomic-embed-text"
fi

echo ""
echo "🧪 Run E2E tests with:"
echo "MILVUS_URI=http://localhost:19530 \\"
echo "CUSTOM_EMBEDDING_URL=http://localhost:11434/api/embeddings \\"
echo "CUSTOM_EMBEDDING_MODEL=nomic-embed-text \\"
echo "CUSTOM_EMBEDDING_VECTORSIZE=768 \\"
echo "E2E_BACKEND=milvus \\"
echo "E2E_MILVUS=1 \\"
echo "uv run pytest tests/e2e/test_mcp_milvus_e2e.py -v -m \"e2e\""

echo ""
echo "📋 Container Management Commands:"
echo "  Stop:    docker stop milvus-simple"
echo "  Start:   docker start milvus-simple"
echo "  Remove:  docker rm milvus-simple"
echo "  Logs:    docker logs milvus-simple"
echo ""
echo "✅ Setup complete! Milvus is ready for E2E testing."