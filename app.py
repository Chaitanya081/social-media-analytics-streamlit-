# app.py
# Final updated, working Social Media Analytics Streamlit app (Option B: full-login background)
# Features:
# - Full background image on the LOGIN page (uses data/SocialMedia1.png if present)
# - Clean Login / Register tabs (prevents duplicate registration)
# - DB stored at data/social_media.db if possible; falls back to temp dir
# - Add / Edit / Delete users and posts (CRUD)
# - Analytics / Performance modules preserved
# - Manual time entry for posts (HH:MM:SS) + validation
# - Passwords hashed with SHA256
# - Robust: creates schema if schema/sql files missing

import streamlit as st
import sqlite3
import pandas as pd
import time
import os
import tempfile
import hashlib
from datetime import datetime

# Try to import create_indexes if analytics module exists
try:
    from analytics.queries import create_indexes
except Exception:
    def create_indexes(conn):
        # fallback: create some simple indexes if tables exist
        try:
            c = conn.cursor()
            c.execute("CREATE INDEX IF NOT EXISTS idx_posts_user ON Posts(user_id);")
            c.execute("CREATE INDEX IF NOT EXISTS idx_posts_created ON Posts(created_at);")
            conn.commit()
        except Exception:
            pass

# -----------------------
# Config + paths
# -----------------------
st.set_page_config(page_title="Social Media Analytics Platform", layout="wide")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

# Prefer repository DB file (so registrations persist if writable there), else fallback to temp
DB_FILE_REPO = os.path.join(DATA_DIR, "social_media.db")
TEMP_DB = os.path.join(tempfile.gettempdir(), "social_media.db")
DB_PATH = DB_FILE_REPO if os.access(DATA_DIR, os.W_OK) else TEMP_DB

# Banner image path (login background). Use data/SocialMedia1.png as requested.
BANNER_FILE = os.path.join("data", "SocialMedia1.png")  # relative path for repo

# -----------------------
# Utility functions
# -----------------------
def sha256(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

# -----------------------
# Ensure DB schema (robust: fallback schema if files missing)
# -----------------------
def ensure_database():
    conn = get_conn()
    c = conn.cursor()

    # If db/schema.sql exists in repo, use it; otherwise create minimal schema
    schema_path = os.path.join(BASE_DIR, "db", "schema.sql")
    if os.path.exists(schema_path):
        try:
            with open(schema_path, "r") as f:
                c.executescript(f.read())
        except Exception:
            pass

    # Minimal fallback schema (safe to run even if tables exist)
    c.execute("""
        CREATE TABLE IF NOT EXISTS Users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            email TEXT UNIQUE,
            created_at TEXT DEFAULT (datetime('now')),
            password TEXT
        );
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS Posts (
            post_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            content TEXT,
            likes INTEGER DEFAULT 0,
            created_at TEXT
        );
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS Comments (
            comment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER,
            user_id INTEGER,
            content TEXT,
            created_at TEXT
        );
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS Relationships (
            follower_id INTEGER,
            following_id INTEGER
        );
    """)
    conn.commit()

    # If sample_data.sql exists and Users empty, load it
    sample_path = os.path.join(BASE_DIR, "db", "sample_data.sql")
    try:
        c.execute("SELECT COUNT(*) FROM Users;")
        cnt = c.fetchone()[0]
    except Exception:
        cnt = 0

    if cnt == 0 and os.path.exists(sample_path):
        try:
            with open(sample_path, "r") as f:
                c.executescript(f.read())
            conn.commit()
        except Exception:
            pass

    # Ensure password column present (PRAGMA idempotent)
    try:
        c.execute("PRAGMA table_info(Users);")
        cols = [r[1] for r in c.fetchall()]
        if "password" not in cols:
            c.execute("ALTER TABLE Users ADD COLUMN password TEXT;")
            conn.commit()
    except Exception:
        pass

    conn.close()

ensure_database()

# -----------------------
# Auth helpers
# -----------------------
def user_by_email(email: str):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT user_id, username, email FROM Users WHERE email=?", (email,))
    row = c.fetchone()
    conn.close()
    return row

def verify_user(email: str, password: str):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT user_id, username, email FROM Users WHERE email=? AND password=?", (email, sha256(password)))
    row = c.fetchone()
    conn.close()
    return row

def create_user(username: str, email: str, password: str):
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO Users (username, email, password, created_at) VALUES (?, ?, ?, ?)",
                  (username, email, sha256(password), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        return True
    except sqlite3.IntegrityError as e:
        return "Email already registered."
    except Exception as e:
        return str(e)
    finally:
        conn.close()

def update_user(user_id: int, username: str, email: str, password: str = None):
    conn = get_conn()
    c = conn.cursor()
    try:
        if password:
            c.execute("UPDATE Users SET username=?, email=?, password=? WHERE user_id=?",
                      (username, email, sha256(password), user_id))
        else:
            c.execute("UPDATE Users SET username=?, email=? WHERE user_id=?",
                      (username, email, user_id))
        conn.commit()
        return True
    except Exception as e:
        return str(e)
    finally:
        conn.close()

def delete_user(user_id: int):
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute("DELETE FROM Users WHERE user_id=?", (user_id,))
        # Optional: cascade delete posts/comments of that user
        c.execute("DELETE FROM Posts WHERE user_id=?", (user_id,))
        c.execute("DELETE FROM Comments WHERE user_id=?", (user_id,))
        conn.commit()
        return True
    except Exception as e:
        return str(e)
    finally:
        conn.close()

# Post helpers
def create_post(user_id: int, content: str, likes: int, created_at: str):
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO Posts (user_id, content, likes, created_at) VALUES (?, ?, ?, ?)",
                  (user_id, content, likes, created_at))
        conn.commit()
        return True
    except Exception as e:
        return str(e)
    finally:
        conn.close()

def update_post(post_id: int, content: str, likes: int):
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute("UPDATE Posts SET content=?, likes=? WHERE post_id=?", (content, likes, post_id))
        conn.commit()
        return True
    except Exception as e:
        return str(e)
    finally:
        conn.close()

def delete_post(post_id: int):
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute("DELETE FROM Posts WHERE post_id=?", (post_id,))
        conn.commit()
        return True
    except Exception as e:
        return str(e)
    finally:
        conn.close()

# -----------------------
# Session state init
# -----------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "user_id" not in st.session_state:
    st.session_state.user_id = None

# -----------------------
# Login page (FULL background)
# -----------------------
def show_login_page():
    # CSS for full-screen login background
    if os.path.exists(BANNER_FILE):
        bg = BANNER_FILE.replace("\\", "/")  # for windows path safety
        css = f"""
        <style>
        .full-bg {{
            width: 100%;
            height: 100vh;
            background-image: url('{bg}');
            background-size: cover;
            background-position: center;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .overlay {{
            position: absolute;
            inset: 0;
            background: rgba(0,0,0,0.45);
            z-index: 0;
        }}
        .login-card {{
            position: relative;
            z-index: 1;
            width: min(920px, 92%);
            max-width: 920px;
            background: rgba(255,255,255,0.06);
            border-radius: 14px;
            padding: 24px;
            box-shadow: 0 8px 30px rgba(0,0,0,0.6);
            backdrop-filter: blur(6px) saturate(120%);
            color: #fff;
            border: 1px solid rgba(255,255,255,0.06);
        }}
        .title {{
            text-align:center;
            font-size:36px;
            font-weight:800;
            margin-bottom:6px;
            color:white;
            text-shadow: 2px 4px 12px rgba(0,0,0,0.6);
        }}
        .subtitle {{
            text-align:center;
            color: rgba(255,255,255,0.9);
            margin-bottom: 18px;
        }}
        </style>
        """
        st.markdown(css, unsafe_allow_html=True)
        st.markdown('<div class="full-bg">', unsafe_allow_html=True)
        st.markdown('<div class="overlay"></div>', unsafe_allow_html=True)
        st.markdown('<div class="login-card">', unsafe_allow_html=True)
    else:
        # fallback: simple centered card without bg
        st.markdown("<div style='display:flex;justify-content:center;margin-top:40px;'>", unsafe_allow_html=True)
        st.markdown("<div style='width:720px;padding:18px;border-radius:12px;background:#f5f5f5;'>", unsafe_allow_html=True)
        st.markdown("<h2 style='text-align:center;'>Social Media Analytics Platform</h2>", unsafe_allow_html=True)

    st.markdown('<div class="title">SOCIAL MEDIA ANALYTICS PLATFORM</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">Sign in to access the dashboard</div>', unsafe_allow_html=True)

    # Tabs
    tab_login, tab_register = st.tabs(["🔑 Login", "🆕 Register"])

    with tab_login:
        with st.form("login_form"):
            login_email = st.text_input("Email", key="login_email")
            login_pw = st.text_input("Password", type="password", key="login_pw")
            remember = st.checkbox("Remember me (session)")
            submitted = st.form_submit_button("Sign In")
            if submitted:
                if not login_email or not login_pw:
                    st.error("Fill both email and password.")
                else:
                    user = verify_user(login_email.strip(), login_pw)
                    if user:
                        st.session_state.logged_in = True
                        st.session_state.user_id = user[0]
                        st.session_state.username = user[1]
                        if remember:
                            st.session_state["remembered_user"] = (login_email.strip(), sha256(login_pw))
                        st.success(f"Welcome back, {user[1]}!")
                        time.sleep(0.6)
                        st.experimental_rerun()
                    else:
                        st.error("Invalid email or password.")

    with tab_register:
        with st.form("register_form"):
            reg_username = st.text_input("Username", key="reg_username")
            reg_email = st.text_input("Email", key="reg_email")
            reg_pw = st.text_input("Password", type="password", key="reg_pw")
            reg_sub = st.form_submit_button("Register")
            if reg_sub:
                if not reg_username or not reg_email or not reg_pw:
                    st.warning("Fill all fields.")
                else:
                    res = create_user(reg_username.strip(), reg_email.strip(), reg_pw)
                    if res is True:
                        st.success("Registration successful — please log in.")
                    else:
                        st.error(res)

    # close wrappers
    if os.path.exists(BANNER_FILE):
        st.markdown("</div></div>", unsafe_allow_html=True)
    else:
        st.markdown("</div></div>", unsafe_allow_html=True)

# -----------------------
# Main app UI (after login)
# -----------------------
def show_main_app():
    # top small header
    st.title("📊 Social Media Analytics Platform (Dashboard)")
    # sidebar
    with st.sidebar:
        st.markdown(f"**👋 Logged in as**  \n**{st.session_state.username}**")
        if st.button("Logout"):
            st.session_state.logged_in = False
            st.session_state.username = ""
            st.session_state.user_id = None
            st.experimental_rerun()
        st.markdown("---")
        module = st.radio("Modules", ["Database Overview", "Analytics", "Performance", "User Management", "Post Management"])
    conn = get_conn()

    # MODULE: Database Overview
    if module == "Database Overview":
        st.header("Database Overview")
        users = pd.read_sql_query("SELECT user_id, username, email, created_at FROM Users ORDER BY user_id DESC", conn)
        posts = pd.read_sql_query("SELECT * FROM Posts ORDER BY created_at DESC", conn)
        st.subheader("Users")
        st.dataframe(users)
        st.subheader("Posts")
        st.dataframe(posts)

    # MODULE: Analytics
    elif module == "Analytics":
        st.header("Analytics")
        option = st.selectbox("Choose Analysis", ["Most Active Users", "Top Influencers", "Trending Posts"])
        start = time.time()
        try:
            if option == "Most Active Users":
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
                if not df.empty:
                    st.bar_chart(df.set_index("username"))
                else:
                    st.info("No activity.")
            elif option == "Top Influencers":
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
                    st.info("No relationships.")
            else:
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
        st.info(f"Query time: {round(time.time() - start, 4)}s")

    # MODULE: Performance
    elif module == "Performance":
        st.header("Performance")
        if st.button("Create Indexes"):
            try:
                create_indexes(conn)
                st.success("Indexes created.")
            except Exception as e:
                st.error(f"Indexing error: {e}")

    # MODULE: User Management (Add / Edit / Delete)
    elif module == "User Management":
        st.header("User Management")
        tabs = st.tabs(["➕ Add User", "🖊️ Edit User", "❌ Delete User", "View Users"])
        # Add
        with tabs[0]:
            with st.form("add_user_form"):
                uname = st.text_input("Username", key="add_un")
                uemail = st.text_input("Email", key="add_em")
                upw = st.text_input("Password", type="password", key="add_pw")
                sub = st.form_submit_button("Add User")
                if sub:
                    if not (uname and uemail and upw):
                        st.warning("Fill all fields.")
                    else:
                        res = create_user(uname.strip(), uemail.strip(), upw)
                        if res is True:
                            st.success("User added.")
                        else:
                            st.error(res)
        # Edit
        with tabs[1]:
            users_df = pd.read_sql_query("SELECT user_id, username, email FROM Users ORDER BY user_id DESC", conn)
            if users_df.empty:
                st.info("No users found.")
            else:
                uid = st.selectbox("Select user to edit", users_df["user_id"],
                                   format_func=lambda x: users_df.loc[users_df["user_id"] == x, "username"].values[0])
                user_row = users_df[users_df["user_id"] == uid].iloc[0]
                new_un = st.text_input("Username", value=user_row["username"], key="edit_un")
                new_em = st.text_input("Email", value=user_row["email"], key="edit_em")
                new_pw = st.text_input("New password (leave blank to keep)", type="password", key="edit_pw")
                if st.button("Update User"):
                    res = update_user(uid, new_un.strip(), new_em.strip(), new_pw if new_pw else None)
                    if res is True:
                        st.success("User updated.")
                    else:
                        st.error(res)
        # Delete
        with tabs[2]:
            users_df = pd.read_sql_query("SELECT user_id, username FROM Users ORDER BY user_id DESC", conn)
            if users_df.empty:
                st.info("No users to delete.")
            else:
                uid = st.selectbox("Select user to delete", users_df["user_id"],
                                   format_func=lambda x: users_df.loc[users_df["user_id"] == x, "username"].values[0],
                                   key="del_user_sel")
                if st.button("Delete User"):
                    res = delete_user(uid)
                    if res is True:
                        st.success("User deleted (and related posts/comments).")
                    else:
                        st.error(res)
        # View
        with tabs[3]:
            st.dataframe(pd.read_sql_query("SELECT user_id, username, email, created_at FROM Users ORDER BY user_id DESC", conn))

    # MODULE: Post Management
    elif module == "Post Management":
        st.header("Post Management")
        tabs = st.tabs(["➕ Add Post", "🖊️ Edit Post", "❌ Delete Post", "View Posts"])
        # Add
        with tabs[0]:
            users_df = pd.read_sql_query("SELECT user_id, username FROM Users ORDER BY user_id DESC", conn)
            if users_df.empty:
                st.info("No users found - add users first.")
            else:
                uid = st.selectbox("Select User", users_df["user_id"],
                                   format_func=lambda x: users_df.loc[users_df["user_id"] == x, "username"].values[0], key="post_add_user")
                content = st.text_area("Content", key="post_add_content")
                likes = st.number_input("Likes", min_value=0, value=0, key="post_add_likes")
                date_input = st.date_input("Date", datetime.now().date(), key="post_add_date")
                time_str = st.text_input("Time (HH:MM:SS)", value=datetime.now().strftime("%H:%M:%S"), key="post_add_time")
                try:
                    datetime.strptime(time_str, "%H:%M:%S")
                    created_at = f"{date_input} {time_str}"
                except ValueError:
                    created_at = None
                    st.warning("Invalid time format. Use HH:MM:SS")
                if st.button("Add Post"):
                    if content and created_at:
                        res = create_post(uid, content, int(likes), created_at)
                        if res is True:
                            st.success("Post added.")
                        else:
                            st.error(res)
        # Edit
        with tabs[1]:
            posts_df = pd.read_sql_query("SELECT post_id, content FROM Posts ORDER BY post_id DESC", conn)
            if posts_df.empty:
                st.info("No posts.")
            else:
                pid = st.selectbox("Select post to edit", posts_df["post_id"],
                                   format_func=lambda x: posts_df.loc[posts_df["post_id"] == x, "content"].values[0], key="post_edit_sel")
                row = pd.read_sql_query("SELECT * FROM Posts WHERE post_id=?", conn, params=(pid,)).iloc[0]
                new_content = st.text_area("Content", value=row["content"], key="post_edit_content")
                new_likes = st.number_input("Likes", min_value=0, value=int(row.get("likes", 0)), key="post_edit_likes")
                if st.button("Update Post"):
                    res = update_post(pid, new_content, int(new_likes))
                    if res is True:
                        st.success("Post updated.")
                    else:
                        st.error(res)
        # Delete
        with tabs[2]:
            posts_df = pd.read_sql_query("SELECT post_id, content FROM Posts ORDER BY post_id DESC", conn)
            if posts_df.empty:
                st.info("No posts to delete.")
            else:
                pid = st.selectbox("Select post to delete", posts_df["post_id"],
                                   format_func=lambda x: posts_df.loc[posts_df["post_id"] == x, "content"].values[0], key="post_del_sel")
                if st.button("Delete Post"):
                    res = delete_post(pid)
                    if res is True:
                        st.success("Post deleted.")
                    else:
                        st.error(res)
        # View
        with tabs[3]:
            st.dataframe(pd.read_sql_query("SELECT * FROM Posts ORDER BY created_at DESC", conn))

    conn.close()

# -----------------------
# App entrypoint
# -----------------------
def main():
    if not st.session_state.logged_in:
        show_login_page()
    else:
        show_main_app()

if __name__ == "__main__":
    main()
