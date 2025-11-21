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
# STREAMLIT PAGE CONFIG
# -------------------------------------------------------
st.set_page_config(page_title="Social Media Analytics Platform", layout="wide")

# -------------------------------------------------------
# DATABASE PATHS (FIX FOR FILE NOT FOUND)
# -------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_SCHEMA = os.path.join(BASE_DIR, "db", "schema.sql")
DB_SAMPLE = os.path.join(BASE_DIR, "db", "sample_data.sql")

TEMP_DIR = tempfile.gettempdir()
DB_PATH = os.path.join(TEMP_DIR, "social_media.db")


# -------------------------------------------------------
# PASSWORD HASHING
# -------------------------------------------------------
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


# -------------------------------------------------------
# DATABASE INITIALIZATION
# -------------------------------------------------------
def ensure_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Load schema.sql
    with open(DB_SCHEMA, "r") as f:
        cursor.executescript(f.read())

    # Add password column if missing
    cursor.execute("PRAGMA table_info(Users);")
    columns = [col[1] for col in cursor.fetchall()]
    if "password" not in columns:
        cursor.execute("ALTER TABLE Users ADD COLUMN password TEXT;")

    # Insert sample data only if DB empty
    cursor.execute("SELECT COUNT(*) FROM Users;")
    if cursor.fetchone()[0] == 0:
        with open(DB_SAMPLE, "r") as f:
            cursor.executescript(f.read())

    conn.commit()
    conn.close()


ensure_database()


# -------------------------------------------------------
# AUTH FUNCTIONS
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
            (username, email, hashed),
        )
        conn.commit()
        conn.close()
        return True

    except Exception as e:
        conn.close()
        return str(e)


# -------------------------------------------------------
# LOGIN / REGISTER PAGE (CLEAN SIMPLE UI)
# -------------------------------------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("📊 Social Media Analytics Platform")
    st.write("Welcome! Please log in to continue.")

    tab1, tab2 = st.tabs(["🔑 Login", "🆕 Register"])

    # Login
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
                st.error("Invalid credentials")

    # Register
    with tab2:
        username = st.text_input("New Username")
        remail = st.text_input("New Email")
        rpass = st.text_input("New Password", type="password")

        if st.button("Register"):
            if username and remail and rpass:
                result = register_user(username, remail, rpass)
                if result is True:
                    st.success("Registration successful! Please login.")
                else:
                    st.error(result)
            else:
                st.warning("Fill all fields")

    st.stop()

# -------------------------------------------------------
# LOGGED-IN UI
# -------------------------------------------------------
st.sidebar.success(f"Logged in as {st.session_state.username}")

if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.rerun()

# DB connection
conn = sqlite3.connect(DB_PATH)

# Sidebar module selection
module = st.sidebar.selectbox(
    "Select Module",
    ["Database Overview", "Analytics", "Performance", "User Management", "Post Management"],
)

# -------------------------------------------------------
# MODULE 1: DATABASE OVERVIEW
# -------------------------------------------------------
if module == "Database Overview":
    st.header("User and Post Overview")
    users = pd.read_sql_query("SELECT user_id, username, email FROM Users;", conn)
    posts = pd.read_sql_query("SELECT * FROM Posts;", conn)

    st.subheader("👥 Users Table")
    st.dataframe(users)

    st.subheader("📝 Posts Table")
    st.dataframe(posts)

# -------------------------------------------------------
# MODULE 2: ANALYTICS
# -------------------------------------------------------
elif module == "Analytics":
    st.header("Analytics Dashboard")

    option = st.selectbox("Select Query", ["Most Active Users", "Top Influencers", "Trending Posts"])

    start = time.time()

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

    st.info(f"Query executed in: {round(time.time() - start, 4)} sec")

# -------------------------------------------------------
# MODULE 3: PERFORMANCE
# -------------------------------------------------------
elif module == "Performance":
    st.header("Performance Optimization")

    if st.button("Create Indexes"):
        create_indexes(conn)
        st.success("Indexes created successfully!")

# -------------------------------------------------------
# MODULE 4: USER MANAGEMENT
# -------------------------------------------------------
elif module == "User Management":
    st.header("Manage Users")
    df_users = pd.read_sql_query("SELECT user_id, username, email FROM Users;", conn)
    st.dataframe(df_users)

# -------------------------------------------------------
# MODULE 5: POST MANAGEMENT
# -------------------------------------------------------
elif module == "Post Management":
    st.header("Manage Posts")

    tab1, tab2 = st.tabs(["Add Post", "Delete Post"])

    # Add Post
    with tab1:
        users_df = pd.read_sql_query("SELECT user_id, username FROM Users;", conn)

        user_id = st.selectbox(
            "Select User",
            users_df["user_id"],
            format_func=lambda x: users_df.loc[users_df["user_id"] == x, "username"].values[0],
        )

        content = st.text_area("Post Content")
        likes = st.number_input("Likes", min_value=0, value=0)

        date = st.date_input("Date", datetime.now().date())
        time_in = st.time_input("Time", datetime.now().time())

        created_at = f"{date} {time_in}"

        if st.button("Add Post"):
            conn.execute(
                "INSERT INTO Posts (user_id, content, likes, created_at) VALUES (?, ?, ?, ?)",
                (user_id, content, likes, created_at),
            )
            conn.commit()
            st.success("Post added successfully!")

        posts_df = pd.read_sql_query("SELECT * FROM Posts;", conn)
        st.dataframe(posts_df)

    # Delete Post
    with tab2:
        posts_df = pd.read_sql_query("SELECT post_id, content FROM Posts;", conn)

        post_id = st.selectbox(
            "Select Post to Delete",
            posts_df["post_id"],
            format_func=lambda x: posts_df.loc[posts_df["post_id"] == x, "content"].values[0],
        )

        if st.button("Delete Post"):
            conn.execute("DELETE FROM Posts WHERE post_id=?", (post_id,))
            conn.commit()
            st.success("Post deleted successfully!")


conn.close()
