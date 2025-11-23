# app.py -- final updated single-file app
import streamlit as st
import sqlite3
import pandas as pd
import time
import os
import tempfile
import hashlib
from datetime import datetime

# try import create_indexes helper (optional)
try:
    from analytics.queries import create_indexes
except Exception:
    def create_indexes(conn):
        # fallback: no-op index creation to keep UI button working
        return

# ----------------------------
# Config
# ----------------------------
st.set_page_config(page_title="Social Media Analytics Platform", layout="wide")

# Paths (works on Streamlit Cloud / local)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_SCHEMA_PATH = os.path.join(BASE_DIR, "db", "schema.sql")
DB_SAMPLE_PATH = os.path.join(BASE_DIR, "db", "sample_data.sql")
TEMP_DIR = tempfile.gettempdir()
DB_PATH = os.path.join(TEMP_DIR, "social_media.db")   # cloud-safe writable DB

# ----------------------------
# Utilities
# ----------------------------
def hash_password(password: str) -> str:
    """Return SHA256 hex digest for password (simple hashing)."""
    return hashlib.sha256(password.encode()).hexdigest()

def file_read_if_exists(path: str):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return None

# ----------------------------
# Database initialization (robust)
# ----------------------------
def ensure_database():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # If schema file exists, use it. Otherwise create fallback schema.
    schema_sql = file_read_if_exists(DB_SCHEMA_PATH)
    if schema_sql:
        cur.executescript(schema_sql)
    else:
        # fallback minimal schema
        cur.executescript("""
        CREATE TABLE IF NOT EXISTS Users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            email TEXT UNIQUE,
            created_at TEXT DEFAULT (datetime('now')),
            password TEXT
        );
        CREATE TABLE IF NOT EXISTS Posts (
            post_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            content TEXT,
            likes INTEGER DEFAULT 0,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS Comments (
            comment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER,
            user_id INTEGER,
            content TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS Relationships (
            follower_id INTEGER,
            following_id INTEGER
        );
        """)

    # Ensure password column exists (safe ALTER if needed)
    cur.execute("PRAGMA table_info(Users);")
    cols = [r[1] for r in cur.fetchall()]
    if "password" not in cols:
        try:
            cur.execute("ALTER TABLE Users ADD COLUMN password TEXT;")
        except Exception:
            pass

    # If Users table empty and sample SQL exists, load it
    cur.execute("SELECT COUNT(*) FROM Users;")
    try:
        user_count = cur.fetchone()[0]
    except Exception:
        user_count = 0

    if user_count == 0:
        sample_sql = file_read_if_exists(DB_SAMPLE_PATH)
        if sample_sql:
            try:
                cur.executescript(sample_sql)
            except Exception:
                # ignore sample loading errors
                pass

    conn.commit()
    conn.close()

ensure_database()

# ----------------------------
# Auth helpers
# ----------------------------
def register_user(username: str, email: str, password: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    hashed = hash_password(password)
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        cur.execute(
            "INSERT INTO Users (username, email, password, created_at) VALUES (?, ?, ?, ?);",
            (username, email, hashed, created_at),
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError as e:
        conn.close()
        return "This email is already registered."
    except Exception as e:
        conn.close()
        return str(e)

def verify_user(email: str, password: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    hashed = hash_password(password)
    cur.execute("SELECT user_id, username, email, created_at FROM Users WHERE email=? AND password=?", (email, hashed))
    row = cur.fetchone()
    conn.close()
    return row  # None if not found

# ----------------------------
# Session state defaults
# ----------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "user_id" not in st.session_state:
    st.session_state.user_id = None

# ----------------------------
# Simple Login / Register page (no background image)
# ----------------------------
if not st.session_state.logged_in:
    st.title("📊 Social Media Analytics Platform")
    st.write("Welcome — please sign in or register to continue.")

    login_tab, register_tab = st.tabs(["🔑 Login", "🆕 Register"])

    with login_tab:
        with st.form("login_form"):
            login_email = st.text_input("Email", key="login_email")
            login_password = st.text_input("Password", type="password", key="login_password")
            remember = st.checkbox("Remember me (session only)", key="remember_me")
            submitted = st.form_submit_button("Sign In")
            if submitted:
                if not login_email or not login_password:
                    st.warning("Please fill both email and password.")
                else:
                    user = verify_user(login_email.strip(), login_password)
                    if user:
                        # user is a tuple (user_id, username, email, created_at)
                        st.session_state.logged_in = True
                        st.session_state.user_id = user[0]
                        st.session_state.username = user[1] or user[2]
                        if remember:
                            st.session_state.remembered = (user[2],)  # minimal session remember
                        st.success(f"Login successful — welcome {st.session_state.username}!")
                        # refresh UI (safe)
                        st.experimental_rerun()
                    else:
                        st.error("Invalid email or password. If you are newly registered, please enter the exact password you set.")

    with register_tab:
        with st.form("register_form"):
            reg_username = st.text_input("New Username", key="reg_username")
            reg_email = st.text_input("New Email", key="reg_email")
            reg_password = st.text_input("New Password", type="password", key="reg_password")
            reg_submit = st.form_submit_button("Register")
            if reg_submit:
                if not (reg_username and reg_email and reg_password):
                    st.warning("Please complete all fields.")
                else:
                    res = register_user(reg_username.strip(), reg_email.strip(), reg_password)
                    if res is True:
                        st.success("Registration successful! Now sign in with your credentials.")
                    else:
                        st.error(f"Registration failed: {res}")

    st.stop()  # keep only login/register until authenticated

# ----------------------------
# Logged-in UI: Sidebar and main modules
# ----------------------------
st.sidebar.markdown(f"**👋 Logged in as**  \n**{st.session_state.username}**")
if st.sidebar.button("🚪 Logout"):
    # clear login state and rerun to show login page
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.user_id = None
    st.experimental_rerun()

# connect DB for app
conn = sqlite3.connect(DB_PATH)

st.header(f"Welcome, {st.session_state.username}")

choice = st.sidebar.selectbox("Select Module", ["Database Overview", "Analytics", "Performance", "User Management", "Post Management"])

# ----------------------------
# 1) Database Overview
# ----------------------------
if choice == "Database Overview":
    st.subheader("Database Overview")
    try:
        df_users = pd.read_sql_query("SELECT user_id, username, email, created_at FROM Users ORDER BY user_id;", conn)
        st.write("### 👥 Users")
        st.dataframe(df_users)
    except Exception as e:
        st.error(f"Failed to read Users table: {e}")

    try:
        df_posts = pd.read_sql_query("SELECT * FROM Posts ORDER BY created_at DESC;", conn)
        st.write("### 📝 Posts")
        st.dataframe(df_posts)
    except Exception as e:
        st.info("No Posts table or no posts yet.")

# ----------------------------
# 2) Analytics
# ----------------------------
elif choice == "Analytics":
    st.subheader("Analytics")
    opt = st.selectbox("Choose Analysis", ["Most Active Users", "Top Influencers", "Trending Posts"])
    start = time.time()

    try:
        if opt == "Most Active Users":
            q = """
            SELECT u.username, (COUNT(p.post_id) + COUNT(c.comment_id)) AS total_activity
            FROM Users u
            LEFT JOIN Posts p ON u.user_id = p.user_id
            LEFT JOIN Comments c ON u.user_id = c.user_id
            GROUP BY u.username
            ORDER BY total_activity DESC
            LIMIT 10;
            """
            df = pd.read_sql_query(q, conn)
            if df.empty:
                st.info("No activity data.")
            else:
                st.bar_chart(df.set_index("username"))
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
            if df.empty:
                st.info("No relationships data.")
            else:
                st.bar_chart(df.set_index("username"))
        else:  # Trending Posts
            q = """
            SELECT p.post_id, p.content, (p.likes + COUNT(c.comment_id)) AS engagement_score
            FROM Posts p
            LEFT JOIN Comments c ON p.post_id = c.post_id
            GROUP BY p.post_id
            ORDER BY engagement_score DESC
            LIMIT 5;
            """
            df = pd.read_sql_query(q, conn)
            if df.empty:
                st.info("No trending posts.")
            else:
                st.dataframe(df)
    except Exception as e:
        st.error(f"Analytics error: {e}")

    st.info(f"Query time: {round(time.time() - start, 4)}s")

# ----------------------------
# 3) Performance
# ----------------------------
elif choice == "Performance":
    st.subheader("Performance")
    if st.button("Create Indexes for Optimization"):
        try:
            create_indexes(conn)
            st.success("Indexes created (or function ran).")
        except Exception as e:
            st.error(f"Index creation failed: {e}")

# ----------------------------
# 4) User Management
# ----------------------------
elif choice == "User Management":
    st.subheader("User Management")

    tab_add, tab_edit, tab_delete, tab_view = st.tabs(["Add User", "Edit User", "Delete User", "View Users"])

    with tab_add:
        a_un = st.text_input("Username (new)", key="um_add_un")
        a_em = st.text_input("Email (new)", key="um_add_em")
        a_pw = st.text_input("Password (new)", type="password", key="um_add_pw")
        if st.button("Add User"):
            if a_un and a_em and a_pw:
                res = register_user(a_un.strip(), a_em.strip(), a_pw)
                if res is True:
                    st.success("User added.")
                else:
                    st.error(res)
            else:
                st.warning("Fill all fields.")

    with tab_edit:
        try:
            users_df = pd.read_sql_query("SELECT user_id, username, email FROM Users ORDER BY user_id;", conn)
        except Exception:
            users_df = pd.DataFrame()
        if users_df.empty:
            st.info("No users available.")
        else:
            uid = st.selectbox("Select user to edit", users_df["user_id"], format_func=lambda x: users_df.loc[users_df["user_id"]==x,"username"].values[0])
            row = users_df[users_df["user_id"]==uid].iloc[0]
            new_un = st.text_input("Username", value=row["username"], key="um_edit_un")
            new_em = st.text_input("Email", value=row["email"], key="um_edit_em")
            new_pw = st.text_input("New Password (leave blank to keep)", type="password", key="um_edit_pw")
            if st.button("Update User"):
                try:
                    if new_pw:
                        conn.execute("UPDATE Users SET username=?, email=?, password=? WHERE user_id=?", (new_un.strip(), new_em.strip(), hash_password(new_pw), uid))
                    else:
                        conn.execute("UPDATE Users SET username=?, email=? WHERE user_id=?", (new_un.strip(), new_em.strip(), uid))
                    conn.commit()
                    st.success("User updated.")
                except Exception as e:
                    st.error(f"Update failed: {e}")

    with tab_delete:
        try:
            users_df = pd.read_sql_query("SELECT user_id, username FROM Users ORDER BY user_id;", conn)
        except Exception:
            users_df = pd.DataFrame()
        if users_df.empty:
            st.info("No users to delete.")
        else:
            uid = st.selectbox("Select user to delete", users_df["user_id"], format_func=lambda x: users_df.loc[users_df["user_id"]==x,"username"].values[0])
            if st.button("Delete User"):
                try:
                    conn.execute("DELETE FROM Users WHERE user_id=?", (uid,))
                    conn.commit()
                    st.success("User deleted.")
                except Exception as e:
                    st.error(f"Deletion failed: {e}")

    with tab_view:
        try:
            st.dataframe(pd.read_sql_query("SELECT user_id, username, email, created_at FROM Users ORDER BY user_id;", conn))
        except Exception as e:
            st.error(f"Could not fetch users: {e}")

# ----------------------------
# 5) Post Management
# ----------------------------
elif choice == "Post Management":
    st.subheader("Post Management")
    tab1, tab2 = st.tabs(["Add Post", "Delete Post"])

    with tab1:
        users_df = pd.read_sql_query("SELECT user_id, username FROM Users ORDER BY user_id;", conn)
        if users_df.empty:
            st.info("No users present — add users first.")
        else:
            uid = st.selectbox("Select User", users_df["user_id"], format_func=lambda x: users_df.loc[users_df["user_id"]==x,"username"].values[0])
            content = st.text_area("Post content")
            likes = st.number_input("Likes", min_value=0, value=0)
            date_input = st.date_input("Date", datetime.now().date())
            time_input = st.time_input("Time", datetime.now().time())
            created_at = f"{date_input} {time_input}"
            if st.button("Add Post"):
                try:
                    conn.execute("INSERT INTO Posts (user_id, content, likes, created_at) VALUES (?, ?, ?, ?);", (uid, content, likes, created_at))
                    conn.commit()
                    st.success("Post added.")
                except Exception as e:
                    st.error(f"Failed to add post: {e}")

        try:
            st.write("Existing posts")
            st.dataframe(pd.read_sql_query("SELECT * FROM Posts ORDER BY created_at DESC;", conn))
        except Exception:
            st.info("No posts yet.")

    with tab2:
        posts_df = pd.read_sql_query("SELECT post_id, content FROM Posts ORDER BY post_id;", conn)
        if posts_df.empty:
            st.info("No posts to delete.")
        else:
            pid = st.selectbox("Select Post", posts_df["post_id"], format_func=lambda x: posts_df.loc[posts_df["post_id"]==x,"content"].values[0])
            if st.button("Delete Post"):
                try:
                    conn.execute("DELETE FROM Posts WHERE post_id=?", (pid,))
                    conn.commit()
                    st.success("Post deleted.")
                except Exception as e:
                    st.error(f"Delete failed: {e}")

# ----------------------------
# Close DB
# ----------------------------
conn.close()
