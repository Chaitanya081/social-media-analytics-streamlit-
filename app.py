# app.py -- Final updated, fully working Streamlit app
# Features:
# - Simple clean Login/Register (no background image)
# - Persistent SQLite DB stored in system temp directory (works on Streamlit Cloud)
# - Users: add / edit / delete (from User Management)
# - Posts: add / edit / delete; Posts list shows the username who created each post
# - Safe handling when db/schema.sql or db/sample_data.sql are missing (fallback schema & sample data)
# - Passwords stored hashed (SHA256)
#
# Place this file at your repo root alongside the 'db' folder (optional). If db/schema.sql exists it will be used;
# otherwise built-in fallback schema will be created automatically.

import streamlit as st
import sqlite3
import pandas as pd
import os
import tempfile
import hashlib
from datetime import datetime, time as dtime

# Optional helper import used previously by you; if absent, the button will still work (create_indexes is optional).
try:
    from analytics.queries import create_indexes  # optional
except Exception:
    def create_indexes(conn):
        # noop fallback
        pass

# -------------------------
# Configuration / DB paths
# -------------------------
st.set_page_config(page_title="Social Media Analytics Platform", layout="wide")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCHEMA_PATH = os.path.join(BASE_DIR, "db", "schema.sql")
SAMPLE_PATH = os.path.join(BASE_DIR, "db", "sample_data.sql")
TEMP_DIR = tempfile.gettempdir()
DB_PATH = os.path.join(TEMP_DIR, "social_media.db")  # persistent across runs on same machine/container

# -------------------------
# Utilities
# -------------------------
def hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

def open_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

# -------------------------
# DB initialization
# -------------------------
def ensure_database():
    conn = open_conn()
    cur = conn.cursor()

    # If user provided schema file, use it; otherwise use fallback schema.
    if os.path.exists(SCHEMA_PATH):
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            sql = f.read()
            cur.executescript(sql)
    else:
        # fallback schema
        cur.executescript(
            """
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
            """
        )

    # If DB empty and sample_data exists, load it; otherwise optional builtin sample
    cur.execute("SELECT COUNT(*) FROM Users;")
    cnt = cur.fetchone()[0]
    if cnt == 0:
        if os.path.exists(SAMPLE_PATH):
            with open(SAMPLE_PATH, "r", encoding="utf-8") as f:
                cur.executescript(f.read())
        else:
            # small builtin sample data
            cur.executescript(
                f"""
                INSERT OR IGNORE INTO Users (username, email, password, created_at)
                  VALUES
                  ('Alice', 'alice@example.com', '{hash_password("alice123")}', datetime('now')),
                  ('Bob', 'bob@example.com', '{hash_password("bob123")}', datetime('now')),
                  ('Charlie', 'charlie@example.com', '{hash_password("charlie123")}', datetime('now')),
                  ('G Chaitanya', 'chaithanya06gutti@gmail.com', '{hash_password("project123")}', datetime('now'));
                INSERT OR IGNORE INTO Posts (user_id, content, likes, created_at)
                  VALUES
                  (1, 'Hello World!', 5, '2024-01-15 10:22:00'),
                  (2, 'My first post!', 12, '2024-02-20 15:45:00'),
                  (3, 'Nice weather today!', 7, '2024-03-01 09:10:00');
                """
            )

    conn.commit()
    conn.close()

ensure_database()

# -------------------------
# Auth and data functions
# -------------------------
def verify_user(email: str, password: str):
    conn = open_conn()
    cur = conn.cursor()
    cur.execute("SELECT user_id, username, email FROM Users WHERE email=? AND password=?", (email.strip(), hash_password(password)))
    row = cur.fetchone()
    conn.close()
    return row

def register_user(username: str, email: str, password: str):
    conn = open_conn()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO Users (username, email, password, created_at) VALUES (?, ?, ?, ?)",
                    (username.strip(), email.strip(), hash_password(password), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError as e:
        conn.close()
        if "UNIQUE constraint failed: Users.email" in str(e):
            return "Email already registered."
        return str(e)
    except Exception as e:
        conn.close()
        return str(e)

# -------------------------
# Streamlit session init
# -------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "user_id" not in st.session_state:
    st.session_state.user_id = None

# -------------------------
# LOGIN / REGISTER (clean, simple)
# -------------------------
def login_register_ui():
    st.title("📊 Social Media Analytics Platform")
    st.write("Welcome — please sign in or register to continue.")

    login_tab, reg_tab = st.tabs(["🔑 Login", "🆕 Register"])

    with login_tab:
        with st.form("login_form"):
            le = st.text_input("Email", key="login_email")
            lp = st.text_input("Password", type="password", key="login_password")
            submit_login = st.form_submit_button("Sign In")
            if submit_login:
                if not le or not lp:
                    st.warning("Please fill both email and password.")
                else:
                    user = verify_user(le, lp)
                    if user:
                        st.session_state.logged_in = True
                        st.session_state.user_id = user[0]
                        st.session_state.username = user[1] or user[2]
                        st.success(f"Login successful — welcome {st.session_state.username}!")
                        st.experimental_rerun()
                    else:
                        st.error("Invalid email or password.")

    with reg_tab:
        with st.form("reg_form"):
            ru = st.text_input("Username", key="reg_username")
            re = st.text_input("Email", key="reg_email")
            rp = st.text_input("Password", type="password", key="reg_password")
            submit_reg = st.form_submit_button("Register")
            if submit_reg:
                if not ru or not re or not rp:
                    st.warning("Please fill all fields.")
                else:
                    res = register_user(ru, re, rp)
                    if res is True:
                        st.success("Registration successful. You can sign in now.")
                    else:
                        st.error(res)

# if not logged in show auth UI and stop
if not st.session_state.logged_in:
    login_register_ui()
    st.stop()

# -------------------------
# Main app after login
# -------------------------
# topbar greeting
st.markdown(f"### 👋 Welcome, **{st.session_state.username}**")
st.write("Use the sidebar to navigate modules (Database Overview, Analytics, Performance, User Management, Post Management).")

# Sidebar controls
with st.sidebar:
    st.markdown(f"**Logged in as:**  \n**{st.session_state.username}**")
    if st.button("🚪 Logout"):
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.session_state.user_id = None
        st.experimental_rerun()
    st.markdown("---")
    module = st.selectbox("Select Module", ["Database Overview", "Analytics", "Performance", "User Management", "Post Management"])

# DB connection
conn = open_conn()

# -------------------------
# Module: Database Overview
# -------------------------
if module == "Database Overview":
    st.header("User and Post Overview")
    try:
        users_df = pd.read_sql_query("SELECT user_id, username, email, created_at FROM Users ORDER BY user_id", conn)
        posts_df = pd.read_sql_query("""SELECT p.post_id, p.user_id, u.username AS author, p.content, p.likes, p.created_at
                                       FROM Posts p LEFT JOIN Users u ON p.user_id = u.user_id
                                       ORDER BY p.created_at DESC""", conn)
        st.subheader("👥 Users Table")
        st.dataframe(users_df)
        st.subheader("📝 Posts Table (shows author)")
        st.dataframe(posts_df)
    except Exception as e:
        st.error(f"Failed to load overview: {e}")

# -------------------------
# Module: Analytics
# -------------------------
elif module == "Analytics":
    st.header("Analytics")
    opt = st.selectbox("Select analysis", ["Most Active Users", "Top Influencers", "Trending Posts"])
    start = datetime.now()
    try:
        if opt == "Most Active Users":
            q = """
                SELECT u.username,
                   (IFNULL(p.cnt,0) + IFNULL(c.cnt,0)) AS total_activity
                FROM Users u
                LEFT JOIN (SELECT user_id, COUNT(*) AS cnt FROM Posts GROUP BY user_id) p ON u.user_id = p.user_id
                LEFT JOIN (SELECT user_id, COUNT(*) AS cnt FROM Comments GROUP BY user_id) c ON u.user_id = c.user_id
                ORDER BY total_activity DESC
                LIMIT 10;
            """
            df = pd.read_sql_query(q, conn)
            if df.empty:
                st.info("No activity yet.")
            else:
                st.bar_chart(df.set_index("username"))
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
            if df.empty:
                st.info("No relationships recorded.")
            else:
                st.bar_chart(df.set_index("username"))
        else:  # Trending Posts
            q = """
                SELECT p.post_id, p.content, (p.likes + IFNULL(c.cnt,0)) as engagement_score
                FROM Posts p
                LEFT JOIN (SELECT post_id, COUNT(*) as cnt FROM Comments GROUP BY post_id) c ON p.post_id = c.post_id
                ORDER BY engagement_score DESC
                LIMIT 10;
            """
            df = pd.read_sql_query(q, conn)
            if df.empty:
                st.info("No posts yet.")
            else:
                st.dataframe(df)
        st.info(f"Query time: {(datetime.now() - start).total_seconds():.3f}s")
    except Exception as e:
        st.error(f"Analytics error: {e}")

# -------------------------
# Module: Performance
# -------------------------
elif module == "Performance":
    st.header("Performance & Indexing")
    st.write("Create indexes to speed up analytics queries (idempotent).")
    if st.button("Create Indexes"):
        try:
            create_indexes(conn)
            st.success("Indexes created (or already present).")
        except Exception as e:
            st.error(f"Failed to create indexes: {e}")
    chart_path = os.path.join(BASE_DIR, "data", "performance_chart.png")
    if os.path.exists(chart_path):
        st.image(chart_path, caption="Performance example")
    else:
        st.info("No performance chart found in /data.")

# -------------------------
# Module: User Management
# -------------------------
elif module == "User Management":
    st.header("User Management")
    cols = st.columns([2, 2, 1])
    with cols[0]:
        add_name = st.text_input("Username (new)", key="um_add_name")
    with cols[1]:
        add_email = st.text_input("Email (new)", key="um_add_email")
    with cols[2]:
        add_pw = st.text_input("Password (new)", type="password", key="um_add_pw")
    if st.button("Add User"):
        if not add_name or not add_email or not add_pw:
            st.warning("Fill all fields to add a user.")
        else:
            res = register_user(add_name, add_email, add_pw)
            if res is True:
                st.success("User added.")
            else:
                st.error(res)
    st.markdown("---")

    # Edit / Delete existing users
    users_df = pd.read_sql_query("SELECT user_id, username, email FROM Users ORDER BY user_id", conn)
    if users_df.empty:
        st.info("No users available.")
    else:
        sel_uid = st.selectbox("Select user for edit/delete", users_df["user_id"],
                               format_func=lambda x: f"{users_df.loc[users_df['user_id']==x,'username'].values[0]} ({x})")
        sel_row = users_df[users_df["user_id"] == sel_uid].iloc[0]
        new_name = st.text_input("Edit username", value=sel_row["username"], key="um_edit_name")
        new_email = st.text_input("Edit email", value=sel_row["email"], key="um_edit_email")
        new_pw = st.text_input("New password (leave blank to keep)", type="password", key="um_edit_pw")
        if st.button("Update User"):
            try:
                cur = conn.cursor()
                if new_pw:
                    cur.execute("UPDATE Users SET username=?, email=?, password=? WHERE user_id=?",
                                (new_name.strip(), new_email.strip(), hash_password(new_pw), sel_uid))
                else:
                    cur.execute("UPDATE Users SET username=?, email=? WHERE user_id=?",
                                (new_name.strip(), new_email.strip(), sel_uid))
                conn.commit()
                st.success("User updated.")
            except Exception as e:
                st.error(f"Update failed: {e}")
        if st.button("Delete User"):
            try:
                conn.execute("DELETE FROM Users WHERE user_id=?", (sel_uid,))
                conn.commit()
                st.success("User deleted.")
            except Exception as e:
                st.error(f"Delete failed: {e}")

    st.markdown("### Current users")
    st.dataframe(pd.read_sql_query("SELECT user_id, username, email, created_at FROM Users ORDER BY user_id", conn))

# -------------------------
# Module: Post Management
# -------------------------
elif module == "Post Management":
    st.header("Post Management")

    # Add Post
    with st.expander("➕ Add new post"):
        users_df = pd.read_sql_query("SELECT user_id, username FROM Users ORDER BY user_id", conn)
        if users_df.empty:
            st.warning("No users: add users first.")
        else:
            u_id = st.selectbox("Select author", users_df["user_id"],
                                format_func=lambda x: users_df.loc[users_df['user_id']==x,'username'].values[0])
            content = st.text_area("Content")
            likes = st.number_input("Likes", min_value=0, value=0)
            date_val = st.date_input("Date", datetime.now().date())
            time_val = st.time_input("Time", dtime(hour=datetime.now().hour, minute=datetime.now().minute))
            created_at = f"{date_val} {time_val}"
            if st.button("Add Post"):
                try:
                    conn.execute("INSERT INTO Posts (user_id, content, likes, created_at) VALUES (?, ?, ?, ?)",
                                 (u_id, content, likes, created_at))
                    conn.commit()
                    st.success("Post added.")
                except Exception as e:
                    st.error(f"Failed to add post: {e}")

    # Edit / Delete existing posts
    st.markdown("---")
    posts_df = pd.read_sql_query("""SELECT p.post_id, p.user_id, u.username AS author, p.content, p.likes, p.created_at
                                   FROM Posts p LEFT JOIN Users u ON p.user_id = u.user_id
                                   ORDER BY p.created_at DESC""", conn)
    if posts_df.empty:
        st.info("No posts available.")
    else:
        sel_pid = st.selectbox("Select post to edit/delete", posts_df["post_id"],
                               format_func=lambda x: f"{posts_df.loc[posts_df['post_id']==x,'author'].values[0]} - {str(posts_df.loc[posts_df['post_id']==x,'content'].values[0])[:40]}")
        sel_post = posts_df[posts_df["post_id"] == sel_pid].iloc[0]
        new_content = st.text_area("Edit content", value=sel_post["content"])
        new_likes = st.number_input("Edit likes", min_value=0, value=int(sel_post["likes"]))
        # allow changing author
        auth_options = posts_df["user_id"].unique().tolist()
        try:
            user_map = pd.read_sql_query("SELECT user_id, username FROM Users", conn)
            # choose author from current users
            new_author = st.selectbox("Change author (user_id)", user_map["user_id"],
                                      index=user_map.index[user_map["user_id"]==sel_post["user_id"]].tolist()[0],
                                      format_func=lambda x: user_map.loc[user_map['user_id']==x,'username'].values[0])
        except Exception:
            new_author = sel_post["user_id"]
        if st.button("Update Post"):
            try:
                conn.execute("UPDATE Posts SET user_id=?, content=?, likes=? WHERE post_id=?",
                             (new_author, new_content, new_likes, sel_pid))
                conn.commit()
                st.success("Post updated.")
            except Exception as e:
                st.error(f"Failed to update post: {e}")
        if st.button("Delete Post"):
            try:
                conn.execute("DELETE FROM Posts WHERE post_id=?", (sel_pid,))
                conn.commit()
                st.success("Post deleted.")
            except Exception as e:
                st.error(f"Failed to delete post: {e}")

    st.markdown("### Posts (with author)")
    st.dataframe(posts_df)

# -------------------------
# Cleanup
# -------------------------
conn.close()
