FACE_TEMPLATE_ANN_QUERY = """
SELECT
    ft.id AS template_id,
    ft.person_id,
    p.student_id,
    p.full_name,
    (ft.embedding <=> CAST(:query_embedding AS vector(512))) AS distance
FROM face_templates AS ft
JOIN persons AS p ON p.id = ft.person_id
WHERE ft.is_active = TRUE
  AND p.is_active = TRUE
ORDER BY ft.embedding <=> CAST(:query_embedding AS vector(512))
LIMIT :k
"""

