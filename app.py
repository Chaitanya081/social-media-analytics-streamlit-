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
# Streamlit Config
# -------------------------------------------------------
st.set_page_config(page_title="Social Media Analytics Platform", layout="wide")

# -------------------------------------------------------
# Database Path
# -------------------------------------------------------
TEMP_DIR = tempfile.gettempdir()
DB_PATH = os.path.join(TEMP_DIR, "social_media.db")

# -------------------------------------------------------
# Helper Functions
# -------------------------------------------------------
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def ensure_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Load schema (this file exists)
    with open("db/schema.sql", "r") as f:
        cursor.executescript(f.read())

    # Add password column if missing
    cursor.execute("PRAGMA table_info(Users);")
    cols = [c[1] for c in cursor.fetchall()]
    if "password" not in cols:
        cursor.execute("ALTER TABLE Users ADD COLUMN password TEXT;")

    conn.commit()
    conn.close()

ensure_database()

# -------------------------------------------------------
# AUTH FUNCTIONS
# -------------------------------------------------------
def verify_user(email, password):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM Users WHERE email=? AND password=?",
        (email, hash_password(password))
    )
    user = cursor.fetchone()
    conn.close()
    return user

def register_user(username, email, password):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO Users (username, email, password) VALUES (?, ?, ?)",
            (username, email, hash_password(password))
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

    st.title("🔐 Login / Register")

    login_tab, register_tab = st.tabs(["Login", "Register"])

    # LOGIN TAB
    with login_tab:
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")

        if st.button("Login"):
            user = verify_user(email, password)
            if user:
                st.session_state.logged_in = True
                st.session_state.username = user[1]
                st.success("Login successful!")
                st.rerun()
            else:
                st.error("Invalid email or password.")

    # REGISTER TAB
    with register_tab:
        username = st.text_input("Username")
        reg_email = st.text_input("New Email")
        reg_password = st.text_input("New Password", type="password")

        if st.button("Register"):
            if username and reg_email and reg_password:
                result = register_user(username, reg_email, reg_password)
                if result is True:
                    st.success("Registration completed! Please log in.")
                else:
                    st.error(result)
            else:
                st.warning("Fill all fields.")

    st.stop()

# -------------------------------------------------------
# MAIN APP (AFTER LOGIN)
# -------------------------------------------------------
st.sidebar.success(f"Logged in as {st.session_state.username}")

if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.rerun()

conn = sqlite3.connect(DB_PATH)

choice = st.sidebar.selectbox(
    "Select Module",
    ["Database Overview", "Analytics", "Performance", "User Management", "Post Management"]
)

# -------------------------------------------------------
# Database Overview
# -------------------------------------------------------
if choice == "Database Overview":
    st.subheader("Users and Posts Overview")
    users = pd.read_sql_query("SELECT user_id, username, email FROM Users;", conn)
    posts = pd.read_sql_query("SELECT * FROM Posts;", conn)
    st.write("### Users")
    st.dataframe(users)
    st.write("### Posts")
    st.dataframe(posts)

# -------------------------------------------------------
# Analytics
# -------------------------------------------------------
elif choice == "Analytics":
    st.subheader("Analytics")

    option = st.selectbox("Choose Analysis", [
        "Most Active Users",
        "Top Influencers",
        "Trending Posts"
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
            ORDER BY total_activity DESC;
            """
            df = pd.read_sql_query(query, conn)
            st.bar_chart(df.set_index("username")) if not df.empty else st.info("No data.")

        elif option == "Top Influencers":
            query = """
            SELECT u.username, COUNT(r.following_id) AS followers
            FROM Users u
            JOIN Relationships r ON u.user_id = r.following_id
            GROUP BY u.username
            ORDER BY followers DESC;
            """
            df = pd.read_sql_query(query, conn)
            st.bar_chart(df.set_index("username")) if not df.empty else st.info("No data.")

        elif option == "Trending Posts":
            query = """
            SELECT p.post_id, p.content,
                (p.likes + COUNT(c.comment_id)) AS engagement_score
            FROM Posts p
            LEFT JOIN Comments c ON p.post_id = c.post_id
            GROUP BY p.post_id
            ORDER BY engagement_score DESC;
            """
            df = pd.read_sql_query(query, conn)
            st.dataframe(df)

        st.info(f"Query Time: {round(time.time() - start, 4)} sec")

    except Exception as e:
        st.error(f"Error: {e}")

# -------------------------------------------------------
# Performance
# -------------------------------------------------------
elif choice == "Performance":
    st.subheader("Database Performance Tuning")
    if st.button("Create Indexes"):
        try:
            create_indexes(conn)
            st.success("Indexes created!")
        except Exception as e:
            st.error(str(e))

# -------------------------------------------------------
# User Management
# -------------------------------------------------------
elif choice == "User Management":
    st.subheader("Manage Users")
    df_users = pd.read_sql_query("SELECT user_id, username, email FROM Users;", conn)
    st.dataframe(df_users)

# -------------------------------------------------------
# Post Management
# -------------------------------------------------------
elif choice == "Post Management":
    st.subheader("Manage Posts")

    add_tab, del_tab = st.tabs(["Add Post", "Delete Post"])

    # ADD
    with add_tab:
        users_df = pd.read_sql_query("SELECT user_id, username FROM Users;", conn)
        if not users_df.empty:
            user_id = st.selectbox("Select User", users_df["user_id"],
                                   format_func=lambda x: users_df.loc[users_df["user_id"]==x,"username"].values[0])

            content = st.text_area("Post Content")
            likes = st.number_input("Likes", min_value=0)
            date_input = st.date_input("Date", datetime.now().date())
            time_input = st.time_input("Time", datetime.now().time())
            created_at = f"{date_input} {time_input}"

            if st.button("Add Post"):
                conn.execute(
                    "INSERT INTO Posts (user_id, content, likes, created_at) VALUES (?, ?, ?, ?)",
                    (user_id, content, likes, created_at)
                )
                conn.commit()
                st.success("Post added!")

    # DELETE
    with del_tab:
        posts = pd.read_sql_query("SELECT post_id, content FROM Posts;", conn)
        if not posts.empty:
            post_id = st.selectbox("Select Post to Delete", posts["post_id"])
            if st.button("Delete"):
                conn.execute("DELETE FROM Posts WHERE post_id=?", (post_id,))
                conn.commit()
                st.success("Post deleted!")

conn.close()
