#!/bin/bash
# Quick script to convert existing teacher curriculums to library_master for testing

set -e

echo "==================================="
echo "Convert Curriculums to Library Type"
echo "==================================="
echo

# Check for DATABASE_URL
if [ -z "$DATABASE_URL" ]; then
  echo "❌ ERROR: DATABASE_URL environment variable not set"
  echo "Usage: DATABASE_URL='postgresql://...' ./convert_to_library_curriculum.sh"
  exit 1
fi

echo "Converting 2 existing teacher curriculums to library_master type..."
echo

# Update 2 existing teacher curriculums to be library_master
psql "$DATABASE_URL" <<SQL
-- Show current state
SELECT id, title, source_type, status
FROM curriculums
WHERE source_type = 'teacher_upload'
LIMIT 5;

-- Update 2 of them to be library_master
UPDATE curriculums
SET
  source_type = 'library_master',
  title = '[LIBRARY] ' || title,
  description = 'Official YouSpeak Library Content - ' || COALESCE(description, ''),
  status = 'published'
WHERE id IN (
  SELECT id
  FROM curriculums
  WHERE source_type = 'teacher_upload'
  LIMIT 2
)
RETURNING id, title, source_type, status;

-- Show final state
SELECT
  source_type,
  COUNT(*) as count
FROM curriculums
GROUP BY source_type;
SQL

echo
echo "✅ Done! Check the output above to see converted curriculums."
echo
echo "To verify via API:"
echo "  curl 'https://api-staging.youspeakhq.com/api/v1/curriculums?source_type=library_master' \\"
echo "    -H 'Authorization: Bearer <token>' | jq '.data[] | {title, source_type}'"
