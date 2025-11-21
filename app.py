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

# Simple clean title
st.markdown(
    "<h1 style='text-align:center; font-size:40px;'>📊 Social Media Analytics Platform</h1>",
    unsafe_allow_html=True
)

# -------------------------------------------------------
# Database Path (Streamlit Cloud Safe)
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

    # Load schema
    with open("db/schema.sql", "r") as f:
        cursor.executescript(f.read())

    # Add password column if needed
    cursor.execute("PRAGMA table_info(Users);")
    columns = [col[1] for col in cursor.fetchall()]
    if "password" not in columns:
        cursor.execute("ALTER TABLE Users ADD COLUMN password TEXT;")
        conn.commit()

    # Insert sample data if empty
    cursor.execute("SELECT COUNT(*) FROM Users;")
    if cursor.fetchone()[0] == 0:
        with open("db/sample_data.sql", "r") as f:
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
# LOGIN SCREEN
# -------------------------------------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:

    st.write("")
    st.write("")

    # centered login container
    with st.container():
        st.markdown("<h3 style='text-align:center;'>Welcome! Please log in to continue.</h3>", unsafe_allow_html=True)

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
                    st.error("Invalid email or password")

        # Register Tab
        with tab2:
            username = st.text_input("New Username")
            reg_email = st.text_input("New Email")
            reg_password = st.text_input("New Password", type="password")

            if st.button("Register"):
                if username and reg_email and reg_password:
                    res = register_user(username, reg_email, reg_password)
                    if res is True:
                        st.success("Registration successful! Please log in.")
                    else:
                        st.error(res)
                else:
                    st.warning("Fill all fields")

    st.stop()

# -------------------------------------------------------
# AFTER LOGIN UI
# -------------------------------------------------------
st.sidebar.success(f"Logged in as {st.session_state.username}")

if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.rerun()

conn = sqlite3.connect(DB_PATH)

# Sidebar Navigation
choice = st.sidebar.selectbox(
    "Select Module",
    ["Database Overview", "Analytics", "Performance", "User Management", "Post Management"]
)

# -------------------------------------------------------
# MODULES
# -------------------------------------------------------

# 1️⃣ Database Overview
if choice == "Database Overview":
    st.subheader("User and Post Overview")
    users = pd.read_sql_query("SELECT user_id, username, email FROM Users;", conn)
    posts = pd.read_sql_query("SELECT * FROM Posts;", conn)

    st.write("### 👥 Users Table")
    st.dataframe(users)

    st.write("### 📝 Posts Table")
    st.dataframe(posts)

# 2️⃣ Analytics
elif choice == "Analytics":
    st.subheader("Complex Analytics")

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
        st.error(e)

# 3️⃣ Performance
elif choice == "Performance":
    st.subheader("Performance Optimization")

    if st.button("Create Indexes"):
        try:
            create_indexes(conn)
            st.success("Indexes created!")
        except Exception as e:
            st.error(e)

# 4️⃣ User Management
elif choice == "User Management":
    st.subheader("Manage Users")
    df = pd.read_sql_query("SELECT user_id, username, email FROM Users;", conn)
    st.dataframe(df)

# 5️⃣ Post Management
elif choice == "Post Management":
    st.subheader("Manage Posts")

    tab1, tab2 = st.tabs(["Add Post", "Delete Post"])

    with tab1:
        users = pd.read_sql_query("SELECT user_id, username FROM Users;", conn)
        user_id = st.selectbox("Select User", users["user_id"],
                               format_func=lambda x: users.loc[users["user_id"] == x, "username"].values[0])
        content = st.text_area("Post Content")
        likes = st.number_input("Likes", min_value=0)

        date = st.date_input("Date", datetime.now().date())
        time_val = st.time_input("Time", datetime.now().time())
        created_at = f"{date} {time_val}"

        if st.button("Add Post"):
            conn.execute(
                "INSERT INTO Posts (user_id, content, likes, created_at) VALUES (?, ?, ?, ?)",
                (user_id, content, likes, created_at)
            )
            conn.commit()
            st.success("Post Added")

    with tab2:
        posts = pd.read_sql_query("SELECT post_id, content FROM Posts;", conn)
        post_id = st.selectbox("Delete Post ID", posts["post_id"],
                               format_func=lambda x: posts.loc[posts["post_id"] == x, "content"].values[0])

        if st.button("Delete Post"):
            conn.execute("DELETE FROM Posts WHERE post_id = ?", (post_id,))
            conn.commit()
            st.success("Post Deleted")

conn.close()
