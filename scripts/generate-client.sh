#!/bin/bash
set -e

# Generate TypeScript types from OpenAPI schema
# Usage: ./scripts/generate-client.sh [output_dir]

OUTPUT_DIR="${1:-../frontend/src/api}"
API_URL="${API_URL:-http://localhost:8000}"

echo "Fetching OpenAPI schema from ${API_URL}..."

# Fetch OpenAPI schema
curl -s "${API_URL}/openapi.json" -o openapi.json

if [ ! -f openapi.json ]; then
    echo "Error: Failed to fetch OpenAPI schema"
    exit 1
fi

echo "Generating TypeScript types..."

# Generate TypeScript types using openapi-typescript
npx openapi-typescript openapi.json -o "${OUTPUT_DIR}/schema.d.ts"

echo "TypeScript types generated at ${OUTPUT_DIR}/schema.d.ts"

# Clean up
rm -f openapi.json

echo "Done!"
