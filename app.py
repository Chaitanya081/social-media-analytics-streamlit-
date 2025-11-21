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
# Streamlit Page Setup
# -------------------------------------------------------
st.set_page_config(page_title="Social Media Analytics Platform", layout="wide")

st.title("📊 Social Media Analytics Platform")
st.caption("Welcome! Please log in to continue.")

# -------------------------------------------------------
# Database File Path (Cloud-safe)
# -------------------------------------------------------
TEMP_DIR = tempfile.gettempdir()
DB_PATH = os.path.join(TEMP_DIR, "social_media.db")

# IMPORTANT — Correct folder paths for schema & sample data
SCHEMA_FILE = os.path.join("db", "schema.sql")
SAMPLE_FILE = os.path.join("db", "sample_data.sql")

# -------------------------------------------------------
# Helper Functions
# -------------------------------------------------------
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def ensure_database():
    """Create database & tables safely, load sample data if needed."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # --- Load schema.sql ---
    if not os.path.exists(SCHEMA_FILE):
        st.error(f"❌ Missing file: {SCHEMA_FILE}")
        st.stop()

    with open(SCHEMA_FILE, "r") as f:
        cursor.executescript(f.read())

    # --- Add password column if missing ---
    cursor.execute("PRAGMA table_info(Users);")
    columns = [c[1] for c in cursor.fetchall()]
    if "password" not in columns:
        cursor.execute("ALTER TABLE Users ADD COLUMN password TEXT;")

    # --- Load sample data only if users table empty ---
    cursor.execute("SELECT COUNT(*) FROM Users;")
    if cursor.fetchone()[0] == 0:
        if not os.path.exists(SAMPLE_FILE):
            st.error(f"❌ Missing file: {SAMPLE_FILE}")
            st.stop()

        with open(SAMPLE_FILE, "r") as f:
            cursor.executescript(f.read())

    conn.commit()
    conn.close()


# Initialize DB
ensure_database()

# -------------------------------------------------------
# Auth Functions
# -------------------------------------------------------
def verify_user(email, password):
    hashed = hash_password(password)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT * FROM Users WHERE email=? AND password=?", (email, hashed))
    user = cur.fetchone()
    conn.close()
    return user


def register_user(username, email, password):
    hashed = hash_password(password)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO Users (username, email, password) VALUES (?, ?, ?)",
            (username, email, hashed)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        conn.close()
        return str(e)

# -------------------------------------------------------
# LOGIN / REGISTER UI
# -------------------------------------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:

    tab1, tab2 = st.tabs(["🔐 Login", "🆕 Register"])

    # ---------------- LOGIN ----------------
    with tab1:
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")

        if st.button("Sign In"):
            user = verify_user(email, password)
            if user:
                st.session_state.logged_in = True
                st.session_state.username = user[1]
                st.success("✅ Login successful!")
                st.rerun()
            else:
                st.error("❌ Invalid email or password")

    # ---------------- REGISTER ----------------
    with tab2:
        username = st.text_input("Choose Username")
        new_email = st.text_input("Your Email")
        new_pass = st.text_input("Create Password", type="password")

        if st.button("Create Account"):
            if username and new_email and new_pass:
                result = register_user(username, new_email, new_pass)
                if result is True:
                    st.success("✅ Registered! You may log in now.")
                else:
                    st.error(f"⚠️ {result}")
            else:
                st.warning("Please fill all fields.")

    st.stop()

# -------------------------------------------------------
# APP AFTER LOGIN
# -------------------------------------------------------
st.sidebar.success(f"👋 Logged in as {st.session_state.username}")

if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.rerun()

conn = sqlite3.connect(DB_PATH)

module = st.sidebar.selectbox(
    "Choose Module:",
    ["Database Overview", "Analytics", "Performance", "User Management", "Post Management"]
)

# -------------------------------------------------------
# 1️⃣ DATABASE OVERVIEW
# -------------------------------------------------------
if module == "Database Overview":
    st.header("📁 Database Overview")

    users = pd.read_sql_query("SELECT user_id, username, email FROM Users", conn)
    posts = pd.read_sql_query("SELECT * FROM Posts", conn)

    st.subheader("Users Table")
    st.dataframe(users)

    st.subheader("Posts Table")
    st.dataframe(posts)

# -------------------------------------------------------
# 2️⃣ ANALYTICS
# -------------------------------------------------------
elif module == "Analytics":
    st.header("📈 Analytics Dashboard")

    option = st.selectbox("Choose Analysis", [
        "Most Active Users",
        "Top Influencers",
        "Trending Posts"
    ])

    start = time.time()

    if option == "Most Active Users":
        q = """
        SELECT u.username, 
               COUNT(p.post_id) + COUNT(c.comment_id) AS total_activity
        FROM Users u
        LEFT JOIN Posts p ON u.user_id = p.user_id
        LEFT JOIN Comments c ON u.user_id = c.user_id
        GROUP BY u.username
        ORDER BY total_activity DESC
        LIMIT 10;
        """
        df = pd.read_sql_query(q, conn)
        st.bar_chart(df.set_index("username"))

    elif option == "Top Influencers":
        q = """
        SELECT u.username, COUNT(r.following_id) AS followers
        FROM Users u
        JOIN Relationships r ON u.user_id = r.following_id
        GROUP BY u.username
        ORDER BY followers DESC LIMIT 10;
        """
        df = pd.read_sql_query(q, conn)
        st.bar_chart(df.set_index("username"))

    elif option == "Trending Posts":
        q = """
        SELECT p.post_id, p.content,
               (p.likes + COUNT(c.comment_id)) AS engagement_score
        FROM Posts p
        LEFT JOIN Comments c ON p.post_id = c.post_id
        GROUP BY p.post_id
        ORDER BY engagement_score DESC LIMIT 5;
        """
        df = pd.read_sql_query(q, conn)
        st.dataframe(df)

    st.info(f"⏱ Query Time: {round(time.time() - start, 4)} seconds")

# -------------------------------------------------------
# 3️⃣ PERFORMANCE
# -------------------------------------------------------
elif module == "Performance":
    st.header("⚙️ Performance")

    if st.button("Create Indexes"):
        try:
            create_indexes(conn)
            st.success("Indexes created successfully!")
        except Exception as e:
            st.error(e)

# -------------------------------------------------------
# 4️⃣ USER MANAGEMENT
# -------------------------------------------------------
elif module == "User Management":
    st.header("👥 User Management")
    df = pd.read_sql_query("SELECT user_id, username, email FROM Users", conn)
    st.dataframe(df)

# -------------------------------------------------------
# 5️⃣ POST MANAGEMENT
# -------------------------------------------------------
elif module == "Post Management":
    st.header("📝 Post Management")

    tab1, tab2 = st.tabs(["Add Post", "Delete Post"])

    # ----- ADD -----
    with tab1:
        users = pd.read_sql_query("SELECT user_id, username FROM Users", conn)
        uid = st.selectbox("Choose User", users["user_id"],
                           format_func=lambda x: users.loc[users.user_id == x, "username"].values[0])

        content = st.text_area("Post Content")
        likes = st.number_input("Likes", min_value=0, value=0)
        date = st.date_input("Date", datetime.now().date())
        time_val = st.time_input("Time", datetime.now().time())
        created_at = f"{date} {time_val}"

        if st.button("Add Post"):
            conn.execute("INSERT INTO Posts (user_id, content, likes, created_at) VALUES (?, ?, ?, ?)",
                         (uid, content, likes, created_at))
            conn.commit()
            st.success("Post added!")

    # ----- DELETE -----
    with tab2:
        posts = pd.read_sql_query("SELECT post_id, content FROM Posts", conn)
        if not posts.empty:
            pid = st.selectbox("Select Post", posts["post_id"],
                               format_func=lambda x: posts.loc[posts.post_id == x, "content"].values[0])

            if st.button("Delete"):
                conn.execute("DELETE FROM Posts WHERE post_id=?", (pid,))
                conn.commit()
                st.success("Post deleted!")

conn.close()
