# app.py -- Final updated, clean login + full modules (no background image)
import streamlit as st
import sqlite3
import pandas as pd
import time
import os
import hashlib
import tempfile
from datetime import datetime

# If you have indexing helper in analytics/queries.py keep this import,
# otherwise comment out or add a no-op function with same name.
try:
    from analytics.queries import create_indexes
except Exception:
    def create_indexes(conn):  # fallback noop
        return

# -------------------------
# Page config
# -------------------------
st.set_page_config(page_title="Social Media Analytics Platform", layout="wide")

# -------------------------
# Paths & DB
# -------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCHEMA_SQL = os.path.join(BASE_DIR, "db", "schema.sql")
SAMPLE_SQL = os.path.join(BASE_DIR, "db", "sample_data.sql")

# Use /tmp for writable persistent storage on cloud instances; if you prefer local file,
# set DB_PATH = os.path.join(BASE_DIR, "social_media.db")
DB_PATH = os.path.join(tempfile.gettempdir(), "social_media.db")

# -------------------------
# Utilities
# -------------------------
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def open_sql_file_safe(path):
    """Return SQL text if path exists, else None (no exception)."""
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return None

# -------------------------
# Initialize DB (safe)
# -------------------------
def ensure_database():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Try to load schema.sql if present; otherwise create minimal schema
    schema_text = open_sql_file_safe(SCHEMA_SQL)
    if schema_text:
        try:
            cur.executescript(schema_text)
        except Exception:
            # Fall back to minimal schema if user-provided schema fails
            schema_text = None

    if not schema_text:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS Users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT,
                email TEXT UNIQUE,
                password TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS Posts (
                post_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                content TEXT,
                likes INTEGER DEFAULT 0,
                created_at TEXT
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS Comments (
                comment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id INTEGER,
                user_id INTEGER,
                content TEXT,
                created_at TEXT
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS Relationships (
                follower_id INTEGER,
                following_id INTEGER
            );
        """)

    # If Users empty and sample_data.sql exists, load it
    cur.execute("SELECT COUNT(*) FROM Users;")
    try:
        users_count = cur.fetchone()[0]
    except Exception:
        users_count = 0

    if users_count == 0:
        sample_text = open_sql_file_safe(SAMPLE_SQL)
        if sample_text:
            try:
                cur.executescript(sample_text)
            except Exception:
                # ignore sample load failure
                pass

    conn.commit()
    conn.close()

ensure_database()

# -------------------------
# Auth helpers
# -------------------------
def verify_user(email: str, password: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    hashed = hash_password(password)
    cur.execute("SELECT user_id, username, email FROM Users WHERE email=? AND password=?", (email, hashed))
    user = cur.fetchone()
    conn.close()
    return user

def register_user(username: str, email: str, password: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    hashed = hash_password(password)
    try:
        cur.execute(
            "INSERT INTO Users (username, email, password, created_at) VALUES (?, ?, ?, ?)",
            (username, email, hashed, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError as e:
        conn.close()
        return "Email already registered."
    except Exception as e:
        conn.close()
        return str(e)

# -------------------------
# Session-state defaults
# -------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "user_email" not in st.session_state:
    st.session_state.user_email = ""

# -------------------------
# Simple CSS (small)
# -------------------------
st.markdown("""
    <style>
    /* keep UI tidy */
    .stApp { background-color: #0f1113; color: #e6e6e6; }
    .login-title { font-size:30px; font-weight:800; margin-bottom:6px; color: #fff; }
    .hero-sub { color: #cfcfcf; margin-bottom:14px; }
    .glass-card { background: rgba(255,255,255,0.02); padding: 18px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.03); }
    </style>
""", unsafe_allow_html=True)

# -------------------------
# LOGIN / REGISTER (CLEAN, NO IMAGE)
# -------------------------
if not st.session_state.logged_in:
    st.title("📊 Social Media Analytics Platform")
    st.markdown('<div class="hero-sub">Welcome! Please log in to continue.</div>', unsafe_allow_html=True)

    tab_login, tab_register = st.tabs(["🔑 Login", "🆕 Register"])

    with tab_login:
        with st.form("login_form"):
            login_email = st.text_input("Email", key="login_email")
            login_pw = st.text_input("Password", type="password", key="login_pw")
            remember = st.checkbox("Remember me (session only)")
            submitted = st.form_submit_button("Sign In")

            if submitted:
                if not login_email or not login_pw:
                    st.warning("Please provide both email and password.")
                else:
                    u = verify_user(login_email.strip(), login_pw)
                    if u:
                        st.session_state.logged_in = True
                        st.session_state.username = u[1] or login_email.strip()
                        st.session_state.user_email = login_email.strip()
                        if remember:
                            st.session_state.remembered = (login_email.strip(), hash_password(login_pw))
                        st.success(f"Login successful — Welcome {st.session_state.username}!")
                        # refresh to show dashboard
                        st.experimental_rerun()
                    else:
                        st.error("Invalid email or password.")

    with tab_register:
        with st.form("register_form"):
            new_un = st.text_input("New Username", key="reg_un")
            new_em = st.text_input("New Email", key="reg_em")
            new_pw = st.text_input("New Password", type="password", key="reg_pw")
            reg_sub = st.form_submit_button("Create account")
            if reg_sub:
                if not new_un or not new_em or not new_pw:
                    st.warning("Please fill all fields.")
                else:
                    res = register_user(new_un.strip(), new_em.strip(), new_pw)
                    if res is True:
                        st.success("Registration successful! You can now log in.")
                    else:
                        st.error(res)

    st.stop()  # keep login-only until user logs in

# -------------------------
# AFTER LOGIN: Sidebar + Modules
# -------------------------
st.sidebar.markdown(f"**👋 Logged in as**  \n**{st.session_state.username}**")
if st.sidebar.button("🚪 Logout"):
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.user_email = ""
    # keep DB and data; just rerun to show login
    st.experimental_rerun()

# open DB connection for modules
conn = sqlite3.connect(DB_PATH)

# Sidebar module select
choice = st.sidebar.selectbox("Select Module",
                              ["Dashboard", "Database Overview", "Analytics", "Performance", "User Management", "Post Management"])

# Dashboard
if choice == "Dashboard":
    st.header(f"Welcome, {st.session_state.username}")
    st.write("This is your dashboard area. Use the sidebar to choose modules.")

# Database Overview
elif choice == "Database Overview":
    st.header("User and Post Overview")
    try:
        users_df = pd.read_sql_query("SELECT user_id, username, email, created_at FROM Users ORDER BY user_id;", conn)
        posts_df = pd.read_sql_query("SELECT * FROM Posts ORDER BY created_at DESC;", conn)
        st.subheader("👥 Users")
        st.dataframe(users_df)
        st.subheader("📝 Posts")
        st.dataframe(posts_df)
    except Exception as e:
        st.error(f"Failed to read tables: {e}")

# Analytics
elif choice == "Analytics":
    st.header("Analytics")
    opt = st.selectbox("Choose Analysis", ["Most Active Users", "Top Influencers", "Trending Posts"])
    start_t = time.time()
    try:
        if opt == "Most Active Users":
            q = """
            SELECT u.username, 
                   (COUNT(p.post_id) + COUNT(c.comment_id)) AS total_activity
            FROM Users u
            LEFT JOIN Posts p ON u.user_id = p.user_id
            LEFT JOIN Comments c ON u.user_id = c.user_id
            GROUP BY u.username
            ORDER BY total_activity DESC
            LIMIT 10;
            """
            df = pd.read_sql_query(q, conn)
            if not df.empty:
                st.bar_chart(df.set_index("username"))
            else:
                st.info("No activity data.")
        elif opt == "Top Influencers":
            q = """
            SELECT u.username, COUNT(r.following_id) AS followers
            FROM Users u
            JOIN Relationships r ON u.user_id = r.following_id
            GROUP BY u.username
            ORDER BY followers DESC
            LIMIT 10;
            """
            df = pd.read_sql_query(q, conn)
            if not df.empty:
                st.bar_chart(df.set_index("username"))
            else:
                st.info("No relationships data.")
        elif opt == "Trending Posts":
            q = """
            SELECT p.post_id, p.content, (p.likes + COUNT(c.comment_id)) AS engagement_score
            FROM Posts p
            LEFT JOIN Comments c ON p.post_id = c.post_id
            GROUP BY p.post_id
            ORDER BY engagement_score DESC
            LIMIT 5;
            """
            df = pd.read_sql_query(q, conn)
            if not df.empty:
                st.dataframe(df)
            else:
                st.info("No trending posts.")
    except Exception as e:
        st.error(f"Analytics error: {e}")
    st.info(f"Query time: {round(time.time() - start_t, 4)}s")

# Performance
elif choice == "Performance":
    st.header("Performance")
    if st.button("Create Indexes for Optimization"):
        try:
            create_indexes(conn)
            st.success("Indexes created.")
        except Exception as e:
            st.error(f"Indexing failed: {e}")

# User Management
elif choice == "User Management":
    st.header("Manage Users")

    # Add user form (works in-app)
    with st.form("add_user_form"):
        st.subheader("➕ Add User")
        au_name = st.text_input("Username", key="au_name")
        au_email = st.text_input("Email", key="au_email")
        au_pw = st.text_input("Password", type="password", key="au_pw")
        au_submit = st.form_submit_button("Add User")
        if au_submit:
            if not (au_name and au_email and au_pw):
                st.warning("Please fill all fields to add a user.")
            else:
                res = register_user(au_name.strip(), au_email.strip(), au_pw)
                if res is True:
                    st.success("User added.")
                else:
                    st.error(res)

    st.markdown("---")
    # List / Edit / Delete user simple view
    try:
        df_users = pd.read_sql_query("SELECT user_id, username, email, created_at FROM Users ORDER BY user_id;", conn)
        st.subheader("Existing Users")
        st.dataframe(df_users)
    except Exception as e:
        st.error(f"Could not load users: {e}")

# Post Management
elif choice == "Post Management":
    st.header("Post Management")
    tab1, tab2 = st.tabs(["➕ Add Post", "❌ Delete Post"])

    with tab1:
        users_df = pd.read_sql_query("SELECT user_id, username FROM Users ORDER BY user_id;", conn)
        if users_df.empty:
            st.info("No users found. Add users first.")
        else:
            uid = st.selectbox("Select User", users_df["user_id"],
                               format_func=lambda x: users_df.loc[users_df["user_id"] == x, "username"].values[0])
            content = st.text_area("Content")
            likes = st.number_input("Likes", min_value=0, value=0)
            date_input = st.date_input("Date", datetime.now().date())
            time_input = st.text_input("Time (HH:MM:SS)", value=datetime.now().strftime("%H:%M:%S"))
            try:
                datetime.strptime(time_input, "%H:%M:%S")
                created_at = f"{date_input} {time_input}"
            except Exception:
                created_at = None
                st.warning("Invalid time format: use HH:MM:SS")

            if st.button("Add Post"):
                if content and created_at:
                    try:
                        conn.execute("INSERT INTO Posts (user_id, content, likes, created_at) VALUES (?, ?, ?, ?)",
                                     (uid, content, likes, created_at))
                        conn.commit()
                        st.success("Post added.")
                    except Exception as e:
                        st.error(f"Add failed: {e}")
                else:
                    st.warning("Provide content and valid time.")

        st.markdown("### All posts")
        st.dataframe(pd.read_sql_query("SELECT * FROM Posts ORDER BY created_at DESC;", conn))

    with tab2:
        posts_df = pd.read_sql_query("SELECT post_id, content FROM Posts ORDER BY post_id DESC;", conn)
        if posts_df.empty:
            st.info("No posts to delete.")
        else:
            pid = st.selectbox("Select post to delete", posts_df["post_id"],
                               format_func=lambda x: posts_df.loc[posts_df["post_id"] == x, "content"].values[0])
            if st.button("Delete Post"):
                try:
                    conn.execute("DELETE FROM Posts WHERE post_id=?", (pid,))
                    conn.commit()
                    st.success("Post deleted.")
                except Exception as e:
                    st.error(f"Delete failed: {e}")

# -------------------------
# Close DB
# -------------------------
conn.close()
