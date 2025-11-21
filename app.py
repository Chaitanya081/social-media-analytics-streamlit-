import streamlit as st
import sqlite3
import pandas as pd
import time
import os
import tempfile
import hashlib
from datetime import datetime
from analytics.queries import create_indexes

# -------------------------------------------------------
# Streamlit Page Config
# -------------------------------------------------------
st.set_page_config(page_title="Social Media Analytics Platform", layout="wide")

st.title("📊 Social Media Analytics Platform")

# -------------------------------------------------------
# Database Path (Streamlit Cloud Safe)
# -------------------------------------------------------
TEMP_DIR = tempfile.gettempdir()
DB_PATH = os.path.join(TEMP_DIR, "social_media.db")

# Correct paths for your folder structure
SCHEMA_FILE = "data/db/schema.sql"
SAMPLE_FILE = "data/db/sample_data.sql"

# -------------------------------------------------------
# Helper Functions
# -------------------------------------------------------
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def ensure_database():
    """Create tables and insert sample data if needed."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Load schema file
    with open(SCHEMA_FILE, "r") as f:
        cursor.executescript(f.read())

    # Add password column if missing
    cursor.execute("PRAGMA table_info(Users);")
    columns = [col[1] for col in cursor.fetchall()]
    if "password" not in columns:
        cursor.execute("ALTER TABLE Users ADD COLUMN password TEXT;")
        conn.commit()

    # Load sample data if empty
    cursor.execute("SELECT COUNT(*) FROM Users;")
    if cursor.fetchone()[0] == 0:
        with open(SAMPLE_FILE, "r") as f:
            cursor.executescript(f.read())

    conn.commit()
    conn.close()

ensure_database()

# -------------------------------------------------------
# Authentication
# -------------------------------------------------------
def verify_user(email, password):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    hashed = hash_password(password)
    cursor.execute("SELECT * FROM Users WHERE email=? AND password=?", (email, hashed))
    user = cursor.fetchone()
    conn.close()
    return user

def register_user(username, email, password):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    hashed = hash_password(password)
    try:
        cursor.execute(
            "INSERT INTO Users (username, email, password) VALUES (?, ?, ?);",
            (username, email, hashed)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        conn.close()
        return str(e)


# -------------------------------------------------------
# Login System
# -------------------------------------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.subheader("Welcome! Please login to continue.")

    tab1, tab2 = st.tabs(["🔑 Login", "🆕 Register"])

    # Login Tab
    with tab1:
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")

        if st.button("Sign In"):
            user = verify_user(email, password)
            if user:
                st.session_state.logged_in = True
                st.session_state.username = user[1]
                st.success("Login successful!")
                st.rerun()
            else:
                st.error("Invalid email or password.")

    # Register Tab
    with tab2:
        username = st.text_input("New Username")
        reg_email = st.text_input("New Email")
        reg_password = st.text_input("New Password", type="password")

        if st.button("Register"):
            if username and reg_email and reg_password:
                result = register_user(username, reg_email, reg_password)
                if result is True:
                    st.success("Registration successful! Now log in.")
                else:
                    st.error(result)
            else:
                st.warning("Please fill all fields.")

    st.stop()

# -------------------------------------------------------
# Main App After Login
# -------------------------------------------------------
st.sidebar.success(f"👋 Logged in as {st.session_state.username}")

# Logout button
if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.rerun()

# Connect DB
conn = sqlite3.connect(DB_PATH)

# Sidebar Modules
choice = st.sidebar.selectbox(
    "Select Module",
    ["Database Overview", "Analytics", "Performance", "User Management", "Post Management"]
)

# -------------------------------------------------------
# Database Overview
# -------------------------------------------------------
if choice == "Database Overview":
    st.subheader("User and Post Overview")
    users = pd.read_sql_query("SELECT user_id, username, email FROM Users;", conn)
    posts = pd.read_sql_query("SELECT * FROM Posts;", conn)

    st.write("### 👥 Users Table")
    st.dataframe(users)

    st.write("### 📝 Posts Table")
    st.dataframe(posts)

# -------------------------------------------------------
# Analytics Module
# -------------------------------------------------------
elif choice == "Analytics":
    st.subheader("Analytics Dashboard")

    option = st.selectbox("Choose Analysis", [
        "Most Active Users", "Top Influencers", "Trending Posts"
    ])

    start = time.time()

    try:
        if option == "Most Active Users":
            query = """
            SELECT u.username,
                   COUNT(p.post_id) + COUNT(c.comment_id) AS total_activity
            FROM Users u
            LEFT JOIN Posts p ON u.user_id = p.user_id
            LEFT JOIN Comments c ON u.user_id = c.user_id
            GROUP BY u.username
            ORDER BY total_activity DESC
            LIMIT 10;
            """
            df = pd.read_sql_query(query, conn)
            st.bar_chart(df.set_index("username"))

        elif option == "Top Influencers":
            query = """
            SELECT u.username, COUNT(r.following_id) AS followers
            FROM Users u
            JOIN Relationships r ON u.user_id = r.following_id
            GROUP BY u.username
            ORDER BY followers DESC
            LIMIT 10;
            """
            df = pd.read_sql_query(query, conn)
            st.bar_chart(df.set_index("username"))

        elif option == "Trending Posts":
            query = """
            SELECT p.post_id, p.content,
                   (p.likes + COUNT(c.comment_id)) AS engagement_score
            FROM Posts p
            LEFT JOIN Comments c ON p.post_id = c.post_id
            GROUP BY p.post_id
            ORDER BY engagement_score DESC
            LIMIT 5;
            """
            df = pd.read_sql_query(query, conn)
            st.dataframe(df)

        st.info(f"Query executed in {round(time.time() - start, 4)} sec")

    except Exception as e:
        st.error(f"Query failed: {e}")

# -------------------------------------------------------
# Performance Module
# -------------------------------------------------------
elif choice == "Performance":
    st.subheader("Database Optimization")

    if st.button("Create Indexes"):
        try:
            create_indexes(conn)
            st.success("Indexes created successfully!")
        except Exception as e:
            st.error(f"Index creation failed: {e}")

# -------------------------------------------------------
# User Management
# -------------------------------------------------------
elif choice == "User Management":
    st.subheader("Manage Users")
    df = pd.read_sql_query("SELECT user_id, username, email FROM Users;", conn)
    st.dataframe(df)

# -------------------------------------------------------
# Post Management
# -------------------------------------------------------
elif choice == "Post Management":
    st.subheader("Manage Posts")

    tab1, tab2 = st.tabs(["Add Post", "Delete Post"])

    # Add
    with tab1:
        user_df = pd.read_sql_query("SELECT user_id, username FROM Users;", conn)
        user_id = st.selectbox("User", user_df["user_id"],
                               format_func=lambda x: user_df.loc[user_df["user_id"] == x, "username"].values[0])

        content = st.text_area("Content")
        likes = st.number_input("Likes", min_value=0, value=0)
        date_input = st.date_input("Date", datetime.now().date())
        time_input = st.time_input("Time", datetime.now().time())
        created_at = f"{date_input} {time_input}"

        if st.button("Add"):
            conn.execute("INSERT INTO Posts (user_id, content, likes, created_at) VALUES (?, ?, ?, ?)",
                         (user_id, content, likes, created_at))
            conn.commit()
            st.success("Post added")

    # Delete
    with tab2:
        df_posts = pd.read_sql_query("SELECT post_id, content FROM Posts;", conn)
        if not df_posts.empty:
            post_id = st.selectbox("Post", df_posts["post_id"])
            if st.button("Delete"):
                conn.execute("DELETE FROM Posts WHERE post_id=?", (post_id,))
                conn.commit()
                st.success("Post deleted")

# Close DB
conn.close()
