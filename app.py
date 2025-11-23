# app.py - final (Option B) - clean UI, login/register, full modules including user mgmt
import streamlit as st
import sqlite3
import pandas as pd
import os
import tempfile
import hashlib
from datetime import datetime
import time

# Optional import used by Performance module: if missing just skip
try:
    from analytics.queries import create_indexes
except Exception:
    def create_indexes(conn):
        # no-op fallback
        pass

# -------------------------
# Page config
# -------------------------
st.set_page_config(page_title="Social Media Analytics Platform", layout="wide")

# -------------------------
# Paths and DB
# -------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCHEMA_PATH = os.path.join(BASE_DIR, "db", "schema.sql")
SAMPLE_SQL_PATH = os.path.join(BASE_DIR, "db", "sample_data.sql")

# Use a temp DB (works on Streamlit Cloud and local). Persists while the instance is alive.
DB_PATH = os.path.join(tempfile.gettempdir(), "social_media_app.db")

# -------------------------
# Utility functions
# -------------------------
def hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

def open_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

# -------------------------
# Ensure DB (safe: handles missing files)
# -------------------------
def ensure_database():
    conn = open_conn()
    cur = conn.cursor()

    # Try load schema from file; fallback to inline schema if missing
    if os.path.exists(SCHEMA_PATH):
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            cur.executescript(f.read())
    else:
        # Minimal fallback schema
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

    # If sample SQL exists and Users table empty, load it; handle missing file gracefully
    try:
        cur.execute("SELECT COUNT(*) FROM Users;")
        cnt = cur.fetchone()[0]
    except Exception:
        cnt = 0

    if cnt == 0:
        if os.path.exists(SAMPLE_SQL_PATH):
            try:
                with open(SAMPLE_SQL_PATH, "r", encoding="utf-8") as f:
                    cur.executescript(f.read())
            except Exception:
                # ignore sample load errors
                pass
        else:
            # add a tiny default sample user so UI isn't empty
            pw = hash_password("project123")
            cur.execute("INSERT OR IGNORE INTO Users (username, email, password) VALUES (?, ?, ?);",
                        ("G Chaitanya", "chaithanya06gutti@gmail.com", pw))
    conn.commit()
    conn.close()

ensure_database()

# -------------------------
# Auth helpers
# -------------------------
def register_user(username: str, email: str, password: str):
    conn = open_conn()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO Users (username, email, password, created_at) VALUES (?, ?, ?, ?);",
                    (username.strip(), email.strip(), hash_password(password), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        return True
    except sqlite3.IntegrityError as e:
        return "Email already registered."
    except Exception as e:
        return str(e)
    finally:
        conn.close()

def verify_user(email: str, password: str):
    conn = open_conn()
    cur = conn.cursor()
    cur.execute("SELECT user_id, username, email FROM Users WHERE email=? AND password=?;",
                (email.strip(), hash_password(password)))
    row = cur.fetchone()
    conn.close()
    return row

# -------------------------
# Session defaults
# -------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "user_id" not in st.session_state:
    st.session_state.user_id = None

# -------------------------
# LOGIN / REGISTER PAGE (simple clean UI)
# -------------------------
if not st.session_state.logged_in:
    st.title("📊 Social Media Analytics Platform")
    st.write("Welcome — please sign in to continue.")
    login_tab, reg_tab = st.tabs(["🔑 Login", "🆕 Register"])

    with login_tab:
        with st.form("login_form", clear_on_submit=False):
            email = st.text_input("Email", value="", placeholder="you@example.com", key="login_email")
            password = st.text_input("Password", type="password", key="login_password")
            remember = st.checkbox("Remember me (session only)", value=False)
            submitted = st.form_submit_button("Sign In")
            if submitted:
                if not email or not password:
                    st.warning("Please provide both email and password.")
                else:
                    user = verify_user(email, password)
                    if user:
                        st.session_state.logged_in = True
                        st.session_state.user_id = user[0]
                        st.session_state.username = user[1] or user[2]
                        if remember:
                            st.session_state.remembered = {"email": email, "pw_hash": hash_password(password)}
                        st.success(f"Welcome back, {st.session_state.username}!")
                        # small delay then rerun to load dashboard
                        time.sleep(0.4)
                        st.experimental_rerun()
                    else:
                        st.error("Invalid email or password. If you haven't registered, please use Register tab.")

    with reg_tab:
        with st.form("register_form", clear_on_submit=True):
            new_username = st.text_input("New Username", key="reg_username")
            new_email = st.text_input("New Email", key="reg_email")
            new_password = st.text_input("New Password", type="password", key="reg_password")
            reg_sub = st.form_submit_button("Register")
            if reg_sub:
                if not new_username or not new_email or not new_password:
                    st.warning("All fields are required.")
                else:
                    res = register_user(new_username, new_email, new_password)
                    if res is True:
                        st.success("Registration successful — please sign in from Login tab.")
                    else:
                        st.error(res)

    st.stop()  # prevent remainder of app until logged in

# -------------------------
# MAIN APP (after login)
# -------------------------
# Sidebar
with st.sidebar:
    st.markdown(f"**👋 Logged in as**  \n**{st.session_state.username}**")
    if st.button("🚪 Logout"):
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.session_state.user_id = None
        # keep remembered credentials if present
        st.experimental_rerun()

conn = open_conn()

st.header("Social Media Analytics Platform")

# Module selector
module = st.sidebar.selectbox("Select Module", ["Dashboard", "Database Overview", "Analytics", "Performance", "User Management", "Post Management"])

# -------------------------
# Dashboard (welcome)
# -------------------------
if module == "Dashboard":
    st.subheader(f"Welcome, {st.session_state.username}")
    st.write("This is your dashboard area. Use the sidebar to open modules like User Management, Analytics, Posts, etc.")

# -------------------------
# Database Overview
# -------------------------
elif module == "Database Overview":
    st.subheader("Database Overview")
    try:
        users = pd.read_sql_query("SELECT user_id, username, email, created_at FROM Users ORDER BY user_id;", conn)
        posts = pd.read_sql_query("SELECT * FROM Posts ORDER BY created_at DESC;", conn)
        st.write("### Users")
        st.dataframe(users)
        st.write("### Posts")
        st.dataframe(posts)
    except Exception as e:
        st.error(f"Failed to load data: {e}")

# -------------------------
# Analytics
# -------------------------
elif module == "Analytics":
    st.subheader("Analytics")
    opt = st.selectbox("Choose analysis", ["Most Active Users", "Top Influencers", "Trending Posts"])
    start_t = time.time()
    try:
        if opt == "Most Active Users":
            q = """
            SELECT u.username,
                   COALESCE(COUNT(p.post_id),0) + COALESCE(SUM(CASE WHEN c.comment_id IS NOT NULL THEN 1 ELSE 0 END),0) AS total_activity
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
            SELECT u.username, COUNT(r.follower_id) AS followers
            FROM Users u
            LEFT JOIN Relationships r ON u.user_id = r.following_id
            GROUP BY u.username
            ORDER BY followers DESC
            LIMIT 10;
            """
            df = pd.read_sql_query(q, conn)
            if not df.empty:
                st.bar_chart(df.set_index("username"))
            else:
                st.info("No relationships data.")
        else:
            q = """
            SELECT p.post_id, p.content, p.likes, COUNT(c.comment_id) AS comments,
                   (p.likes + COUNT(c.comment_id)) AS engagement_score
            FROM Posts p
            LEFT JOIN Comments c ON p.post_id = c.post_id
            GROUP BY p.post_id
            ORDER BY engagement_score DESC
            LIMIT 10;
            """
            df = pd.read_sql_query(q, conn)
            if not df.empty:
                st.dataframe(df)
            else:
                st.info("No posts available.")
        st.info(f"Query time: {round(time.time() - start_t, 4)}s")
    except Exception as e:
        st.error(f"Analytics error: {e}")

# -------------------------
# Performance
# -------------------------
elif module == "Performance":
    st.subheader("Performance / Indexing")
    if st.button("Create Indexes (optional)"):
        try:
            create_indexes(conn)
            st.success("Indexes created (if function provided).")
        except Exception as e:
            st.error(f"Index creation failed: {e}")

# -------------------------
# User Management (full add / edit / delete)
# -------------------------
elif module == "User Management":
    st.subheader("Manage Users")

    tab_add, tab_edit, tab_delete, tab_view = st.tabs(["➕ Add User", "✏️ Edit User", "🗑️ Delete User", "👥 View Users"])

    # Add user
    with tab_add:
        with st.form("add_user_form"):
            add_un = st.text_input("Username")
            add_em = st.text_input("Email")
            add_pw = st.text_input("Password", type="password")
            add_sub = st.form_submit_button("Add User")
            if add_sub:
                if not add_un or not add_em or not add_pw:
                    st.warning("Fill all fields.")
                else:
                    res = register_user(add_un, add_em, add_pw)
                    if res is True:
                        st.success("User added.")
                    else:
                        st.error(res)

    # Edit user
    with tab_edit:
        df_users = pd.read_sql_query("SELECT user_id, username, email FROM Users ORDER BY user_id;", conn)
        if not df_users.empty:
            selected = st.selectbox("Select user to edit", df_users["user_id"], format_func=lambda x: df_users.loc[df_users["user_id"]==x, "username"].values[0])
            row = df_users[df_users["user_id"]==selected].iloc[0]
            new_un = st.text_input("Username", value=row["username"])
            new_em = st.text_input("Email", value=row["email"])
            new_pw = st.text_input("New Password (leave blank to keep)", type="password")
            if st.button("Update User"):
                try:
                    if new_pw:
                        conn.execute("UPDATE Users SET username=?, email=?, password=? WHERE user_id=?;",
                                     (new_un.strip(), new_em.strip(), hash_password(new_pw), selected))
                    else:
                        conn.execute("UPDATE Users SET username=?, email=? WHERE user_id=?;",
                                     (new_un.strip(), new_em.strip(), selected))
                    conn.commit()
                    st.success("User updated.")
                except Exception as e:
                    st.error(f"Update failed: {e}")
        else:
            st.info("No users to edit.")

    # Delete user
    with tab_delete:
        df_users = pd.read_sql_query("SELECT user_id, username FROM Users ORDER BY user_id;", conn)
        if not df_users.empty:
            sel_del = st.selectbox("Select user to delete", df_users["user_id"], format_func=lambda x: df_users.loc[df_users["user_id"]==x, "username"].values[0])
            if st.button("Delete User"):
                try:
                    conn.execute("DELETE FROM Users WHERE user_id=?;", (sel_del,))
                    conn.commit()
                    st.success("User deleted.")
                except Exception as e:
                    st.error(f"Delete failed: {e}")
        else:
            st.info("No users to delete.")

    # View users
    with tab_view:
        st.write(pd.read_sql_query("SELECT user_id, username, email, created_at FROM Users ORDER BY user_id;", conn))

# -------------------------
# Post Management
# -------------------------
elif module == "Post Management":
    st.subheader("Post Management")
    tab1, tab2 = st.tabs(["➕ Add Post", "❌ Delete Post"])

    with tab1:
        users_df = pd.read_sql_query("SELECT user_id, username FROM Users ORDER BY user_id;", conn)
        if users_df.empty:
            st.warning("No users exist yet - create a user first.")
        else:
            uid = st.selectbox("Select User", users_df["user_id"], format_func=lambda x: users_df.loc[users_df["user_id"]==x,"username"].values[0])
            content = st.text_area("Content")
            likes = st.number_input("Likes", min_value=0, value=0)
            date = st.date_input("Date", datetime.now().date())
            t_input = st.time_input("Time", datetime.now().time())
            created_at = f"{date} {t_input}"
            if st.button("Add Post"):
                try:
                    conn.execute("INSERT INTO Posts (user_id, content, likes, created_at) VALUES (?, ?, ?, ?);",
                                 (uid, content, likes, created_at))
                    conn.commit()
                    st.success("Post added.")
                except Exception as e:
                    st.error(f"Failed to add post: {e}")

    with tab2:
        posts = pd.read_sql_query("SELECT post_id, content FROM Posts ORDER BY post_id DESC;", conn)
        if posts.empty:
            st.info("No posts to delete.")
        else:
            pid = st.selectbox("Select post to delete", posts["post_id"], format_func=lambda x: posts.loc[posts["post_id"]==x,"content"].values[0])
            if st.button("Delete Post"):
                try:
                    conn.execute("DELETE FROM Posts WHERE post_id=?;", (pid,))
                    conn.commit()
                    st.success("Post deleted.")
                except Exception as e:
                    st.error(f"Delete failed: {e}")

# Close connection at end
conn.close()
