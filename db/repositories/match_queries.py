FACE_TEMPLATE_ANN_QUERY = """
SELECT
    ft.id AS template_id,
    ft.person_id,
    p.student_id,
    p.full_name,
    p.email,
    p.class_id,
    c.class_code,
    c.class_name,
    (ft.embedding <=> CAST(:query_embedding AS vector(512))) AS distance
FROM face_templates AS ft
JOIN persons AS p ON p.id = ft.person_id
LEFT JOIN classes AS c ON c.id = p.class_id
WHERE ft.is_active = TRUE
  AND ft.deleted_at IS NULL
  AND p.is_active = TRUE
  AND p.is_deleted = FALSE
ORDER BY ft.embedding <=> CAST(:query_embedding AS vector(512))
LIMIT :k
"""

FACE_TEMPLATE_CLASS_SCOPED_ANN_QUERY = """
SELECT
    ft.id AS template_id,
    ft.person_id,
    p.student_id,
    p.full_name,
    p.email,
    p.class_id,
    c.class_code,
    c.class_name,
    (ft.embedding <=> CAST(:query_embedding AS vector(512))) AS distance
FROM face_templates AS ft
JOIN persons AS p ON p.id = ft.person_id
LEFT JOIN classes AS c ON c.id = p.class_id
WHERE ft.is_active = TRUE
  AND ft.deleted_at IS NULL
  AND p.is_active = TRUE
  AND p.is_deleted = FALSE
  AND p.class_id = :class_id
ORDER BY ft.embedding <=> CAST(:query_embedding AS vector(512))
LIMIT :k
"""
