def create_indexes(conn):
    """Create necessary indexes to improve query performance."""
    queries = [
        "CREATE INDEX IF NOT EXISTS idx_user_created_at ON Users(created_at);",
        "CREATE INDEX IF NOT EXISTS idx_post_user_id ON Posts(user_id);",
        "CREATE INDEX IF NOT EXISTS idx_comment_post_id ON Comments(post_id);",
        "CREATE INDEX IF NOT EXISTS idx_relationship_following ON Relationships(following_id);"
    ]
    cursor = conn.cursor()
    for q in queries:
        cursor.execute(q)
    conn.commit()
