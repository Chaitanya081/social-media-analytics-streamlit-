import streamlit as st
import sqlite3
import pandas as pd
import hashlib
import os
import tempfile
import time
from datetime import datetime
from analytics.queries import create_indexes

# -------------------------------------------------------
# Streamlit Config
# -------------------------------------------------------
st.set_page_config(page_title="Social Media Analytics Platform", layout="wide")

# -------------------------------------------------------
# Database Path (Cloud Safe)
# -------------------------------------------------------
TEMP_DIR = tempfile.gettempdir()
DB_PATH = os.path.join(TEMP_DIR, "social_media.db")

# -------------------------------------------------------
# Password Hashing
# -------------------------------------------------------
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# -------------------------------------------------------
# Ensure Database Exists
# -------------------------------------------------------
def ensure_database():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Load schema
    with open("db/schema.sql", "r") as f:
        cur.executescript(f.read())

    # Add password column if missing
    cur.execute("PRAGMA table_info(Users);")
    cols = [c[1] for c in cur.fetchall()]
    if "password" not in cols:
        cur.execute("ALTER TABLE Users ADD COLUMN password TEXT;")
        conn.commit()

    # Insert sample data if empty
    cur.execute("SELECT COUNT(*) FROM Users;")
    if cur.fetchone()[0] == 0:
        with open("db/sample_data.sql", "r") as f:
            cur.executescript(f.read())

    conn.commit()
    conn.close()

ensure_database()

# -------------------------------------------------------
# Authentication
# -------------------------------------------------------
def verify_user(email, password):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    hashed = hash_password(password)
    cur.execute("SELECT * FROM Users WHERE email=? AND password=?", (email, hashed))
    user = cur.fetchone()
    conn.close()
    return user

def register_user(username, email, password):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    hashed = hash_password(password)
    try:
        cur.execute(
            "INSERT INTO Users (username, email, password) VALUES (?, ?, ?)",
            (username, email, hashed),
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        conn.close()
        return str(e)

# -------------------------------------------------------
# LOGIN PAGE
# -------------------------------------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:

    st.subheader("🔐 Login to Social Media Analytics Platform")
    login_tab, register_tab = st.tabs(["Login", "Register"])

    # LOGIN TAB
    with login_tab:
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")

        if st.button("Sign In"):
            user = verify_user(email, password)
            if user:
                st.session_state.logged_in = True
                st.session_state.username = user[1]   # username
                st.success(f"Welcome {user[1]}!")
                st.rerun()
            else:
                st.error("Invalid credentials")

    # REGISTER TAB
    with register_tab:
        username = st.text_input("New Username")
        remail = st.text_input("New Email")
        rpass = st.text_input("New Password", type="password")

        if st.button("Register Account"):
            if username and remail and rpass:
                result = register_user(username, remail, rpass)
                if result is True:
                    st.success("Registration successful. Please log in.")
                else:
                    st.error(result)
            else:
                st.warning("All fields are required.")

    st.stop()

# -------------------------------------------------------
# AFTER LOGIN
# -------------------------------------------------------
st.sidebar.success(f"Logged in as {st.session_state.username}")
if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.rerun()

conn = sqlite3.connect(DB_PATH)

module = st.sidebar.selectbox(
    "Select Module",
    ["Dashboard", "User Management", "Analytics", "Post Management", "Performance"]
)

# -------------------------------------------------------
# DASHBOARD
# -------------------------------------------------------
if module == "Dashboard":
    st.header("📊 Social Media Analytics Dashboard")

    users = pd.read_sql_query("SELECT COUNT(*) AS total FROM Users", conn)
    posts = pd.read_sql_query("SELECT COUNT(*) AS total FROM Posts", conn)
    comments = pd.read_sql_query("SELECT COUNT(*) AS total FROM Comments", conn)

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Users", users["total"][0])
    col2.metric("Total Posts", posts["total"][0])
    col3.metric("Total Comments", comments["total"][0])

# -------------------------------------------------------
# USER MANAGEMENT
# -------------------------------------------------------
elif module == "User Management":
    st.header("👤 Manage Users")
    df = pd.read_sql_query("SELECT user_id, username, email FROM Users", conn)
    st.dataframe(df)

# -------------------------------------------------------
# ANALYTICS
# -------------------------------------------------------
elif module == "Analytics":
    st.header("📈 Advanced Analytics")

    query_option = st.selectbox(
        "Choose Analysis",
        ["Most Active Users", "Top Influencers", "Trending Posts"]
    )

    start = time.time()

    if query_option == "Most Active Users":
        query = """
        SELECT u.username,
               COUNT(p.post_id) + COUNT(c.comment_id) AS activity
        FROM Users u
        LEFT JOIN Posts p ON u.user_id = p.user_id
        LEFT JOIN Comments c ON u.user_id = c.user_id
        GROUP BY u.username
        ORDER BY activity DESC
        LIMIT 10;
        """

    elif query_option == "Top Influencers":
        query = """
        SELECT u.username, COUNT(r.following_id) AS followers
        FROM Users u
        JOIN Relationships r ON u.user_id = r.following_id
        GROUP BY u.username
        ORDER BY followers DESC
        LIMIT 10;
        """

    else:
        query = """
        SELECT p.post_id, p.content,
               (p.likes + COUNT(c.comment_id)) AS engagement
        FROM Posts p
        LEFT JOIN Comments c ON p.post_id = c.post_id
        GROUP BY p.post_id
        ORDER BY engagement DESC
        LIMIT 5;
        """

    df = pd.read_sql_query(query, conn)
    st.dataframe(df)
    st.info(f"Query executed in {round(time.time() - start, 4)} sec")

# -------------------------------------------------------
# POST MANAGEMENT
# -------------------------------------------------------
elif module == "Post Management":
    st.header("📝 Manage Posts")

    add_tab, delete_tab = st.tabs(["Add Post", "Delete Post"])

    # --- ADD POST ---
    with add_tab:
        users = pd.read_sql_query("SELECT user_id, username FROM Users", conn)
        uid = st.selectbox(
            "Select User",
            users["user_id"],
            format_func=lambda x: users.loc[users.user_id == x, "username"].iloc[0]
        )
        content = st.text_area("Post Content")
        likes = st.number_input("Likes", min_value=0, value=0)
        created = f"{datetime.now().date()} {datetime.now().time()}"

        if st.button("Add Post"):
            conn.execute(
                "INSERT INTO Posts (user_id, content, likes, created_at) VALUES (?, ?, ?, ?)",
                (uid, content, likes, created)
            )
            conn.commit()
            st.success("Post added!")

    # --- DELETE POST ---
    with delete_tab:
        posts = pd.read_sql_query("SELECT post_id, content FROM Posts", conn)
        if not posts.empty:
            pid = st.selectbox(
                "Select Post to Delete",
                posts["post_id"],
                format_func=lambda x: posts.loc[posts.post_id == x, "content"].iloc[0]
            )
            if st.button("Delete Post"):
                conn.execute("DELETE FROM Posts WHERE post_id=?", (pid,))
                conn.commit()
                st.success("Deleted!")
        else:
            st.info("No posts available.")

# -------------------------------------------------------
# PERFORMANCE
# -------------------------------------------------------
elif module == "Performance":
    st.header("⚡ Performance Optimization")
    if st.button("Create Indexes"):
        try:
            create_indexes(conn)
            st.success("Indexes created successfully!")
        except Exception as e:
            st.error(f"Error: {e}")

conn.close()
