#!/usr/bin/env bash
# End-to-end demo — show the interviewer the API works.
# Run: ./demo.sh

set -euo pipefail

API="${API:-http://localhost:8000}"

echo "=== 1. Health check ==="
curl -fsS "$API/healthz" | jq .
echo

echo "=== 2. OpenAPI spec is available ==="
curl -fsS "$API/openapi.json" | jq '.info.title, .info.version'
echo

echo "=== 3. Search org_alpha (full column config) ==="
curl -fsS "$API/v1/employees/search?limit=3" -H "X-Org-Id: org_alpha" | jq .
echo

echo "=== 4. Search org_beta (different column config — no email) ==="
curl -fsS "$API/v1/employees/search?limit=3" -H "X-Org-Id: org_beta" | jq .
echo

echo "=== 5. Status filter ==="
curl -fsS "$API/v1/employees/search?statuses=active&limit=2" -H "X-Org-Id: org_alpha" | jq '.results | length'
echo

echo "=== 6. Cursor pagination ==="
CURSOR=$(curl -fsS "$API/v1/employees/search?limit=3" -H "X-Org-Id: org_alpha" | jq -r '.next_cursor')
echo "next_cursor: $CURSOR"
curl -fsS "$API/v1/employees/search?limit=3&cursor=$CURSOR" -H "X-Org-Id: org_alpha" | jq '.results[].id // .results[].first_name'
echo

echo "=== 7. Missing tenant → 401 ==="
curl -s -o /dev/null -w "HTTP %{http_code}\n" "$API/v1/employees/search"
echo

echo "=== 8. Trigger rate limit (30 fast requests) ==="
for i in $(seq 1 30); do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
      "$API/v1/employees/search?limit=1" \
      -H "X-Org-Id: org_alpha" \
      -H "X-Principal-Id: demo-user")
  printf "%s " "$STATUS"
done
echo
echo "(expect a stream of 200s, then 429s once the bucket drains)"
