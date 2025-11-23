# app.py -- Final full working code (Option B: full-background login)
import streamlit as st
import sqlite3
import pandas as pd
import time
import os
import tempfile
import hashlib
from datetime import datetime

# Optional analytics helper (if you have analytics/queries.py)
try:
    from analytics.queries import create_indexes
except Exception:
    def create_indexes(conn):
        # fallback no-op
        return

# ---------------------------------------------------------
# Config
# ---------------------------------------------------------
st.set_page_config(page_title="Social Media Analytics Platform", layout="wide")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Banner file you said you saved as SocialMedia1.png in data/
BANNER_FILE = os.path.join(BASE_DIR, "data", "SocialMedia1.png")

# DB path (use a writable tmp dir so Streamlit Cloud is fine)
TEMP_DIR = tempfile.gettempdir()
DB_PATH = os.path.join(TEMP_DIR, "social_media.db")

# ---------------------------------------------------------
# Utilities
# ---------------------------------------------------------
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def read_file_if_exists(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return None

# ---------------------------------------------------------
# Ensure DB & Schema (safe: uses db/schema.sql if present, otherwise fallback)
# ---------------------------------------------------------
def ensure_database():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    schema_path = os.path.join(BASE_DIR, "db", "schema.sql")
    sample_path = os.path.join(BASE_DIR, "db", "sample_data.sql")

    schema_text = read_file_if_exists(schema_path)
    if schema_text:
        try:
            cur.executescript(schema_text)
        except Exception:
            # if schema.sql has errors, fall back to default
            schema_text = None

    if not schema_text:
        # fallback schema
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

    # If DB empty, optionally load sample_data.sql if exists
    try:
        cur.execute("SELECT COUNT(*) FROM Users;")
        cnt = cur.fetchone()[0]
    except Exception:
        cnt = 0

    if cnt == 0:
        sample_text = read_file_if_exists(sample_path)
        if sample_text:
            try:
                cur.executescript(sample_text)
            except Exception:
                pass
        else:
            # minimal sample user so UI isn't empty
            cur.execute("INSERT OR IGNORE INTO Users (username, email, password) VALUES (?, ?, ?)",
                        ("admin", "admin@example.com", hash_password("admin123")))
            cur.execute("INSERT OR IGNORE INTO Users (username, email, password) VALUES (?, ?, ?)",
                        ("alice", "alice@example.com", hash_password("alice123")))
            cur.execute("INSERT OR IGNORE INTO Posts (user_id, content, likes, created_at) VALUES (?, ?, ?, ?)",
                        (1, "Welcome to the platform!", 5, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

    conn.commit()
    conn.close()

ensure_database()

# ---------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------
def verify_user(email: str, password: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    h = hash_password(password)
    cur.execute("SELECT user_id, username, email FROM Users WHERE email=? AND password=?", (email, h))
    row = cur.fetchone()
    conn.close()
    return row  # None or (user_id, username, email)

def register_user(username: str, email: str, password: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # prevent duplicate email
    cur.execute("SELECT user_id FROM Users WHERE email=?", (email,))
    if cur.fetchone():
        conn.close()
        return "Email already registered."
    try:
        cur.execute("INSERT INTO Users (username, email, password, created_at) VALUES (?, ?, ?, ?)",
                    (username, email, hash_password(password), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        conn.close()
        return str(e)

# ---------------------------------------------------------
# Session state defaults
# ---------------------------------------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "username" not in st.session_state:
    st.session_state.username = ""
if "remembered" not in st.session_state:
    st.session_state.remembered = False

# ---------------------------------------------------------
# CSS & full-screen background for login (Option B)
# (we will only show the full background on the login screen;
#  after login the main app uses normal layout)
# ---------------------------------------------------------
LOGIN_CSS = f"""
<style>
/* full-page background only for login view */
.login-bg {{
  position: fixed;
  inset: 0;
  background: url("data/SocialMedia1.png") center/cover no-repeat;
  filter: brightness(0.7);
  z-index: -1;
}}
/* overlay to darken and improve contrast */
.login-overlay {{
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.4);
  z-index: -1;
}}
/* center glass box */
.login-center {{
  display:flex;
  align-items:center;
  justify-content:center;
  min-height: 80vh;
  padding: 24px;
}}
.login-card {{
  width: min(760px, 96%);
  background: rgba(255,255,255,0.06);
  border-radius: 12px;
  padding: 22px;
  color: #fff;
  backdrop-filter: blur(6px) saturate(120%);
  border: 1px solid rgba(255,255,255,0.06);
  box-shadow: 0 8px 30px rgba(0,0,0,0.6);
}}
.login-title {{
  text-align:center; font-size:28px; font-weight:800; margin-bottom:6px;
  color: #fff; text-shadow: 2px 3px 8px rgba(0,0,0,0.6);
}}
.login-sub {{ text-align:center; color:rgba(255,255,255,0.9); margin-bottom:14px; }}
.stTextInput>div>div>input, .stTextArea>div>div>textarea {{
  background: rgba(0,0,0,0.45) !important;
  border-radius: 8px !important;
  color: #fff !important;
}}
</style>
"""

# If the image exists in repo, use it; else fallback to simple header
if os.path.exists(os.path.join(BASE_DIR, "data", "SocialMedia1.png")):
    st.markdown('<div class="login-bg"></div><div class="login-overlay"></div>', unsafe_allow_html=True)
    st.markdown(LOGIN_CSS, unsafe_allow_html=True)

# ---------------------------------------------------------
# LOGIN / REGISTER UI
# ---------------------------------------------------------
if not st.session_state.logged_in:
    # show centered glass card for login/register
    st.markdown('<div class="login-center">', unsafe_allow_html=True)
    st.markdown('<div class="login-card">', unsafe_allow_html=True)
    st.markdown('<div class="login-title">SOCIAL MEDIA ANALYTICS PLATFORM</div>', unsafe_allow_html=True)
    st.markdown('<div class="login-sub">Please sign in or register to continue</div>', unsafe_allow_html=True)

    tabs = st.tabs(["🔑 Login", "🆕 Register"])
    with tabs[0]:
        with st.form("login_form", clear_on_submit=False):
            lemail = st.text_input("Email", key="login_email")
            lpass = st.text_input("Password", type="password", key="login_password")
            remember = st.checkbox("Remember me (session only)")
            submitted = st.form_submit_button("Sign In")
            if submitted:
                if not lemail or not lpass:
                    st.error("Please provide email and password.")
                else:
                    user = verify_user(lemail.strip(), lpass)
                    if user:
                        st.session_state.logged_in = True
                        st.session_state.user_id = user[0]
                        st.session_state.username = user[1]
                        st.session_state.remembered = bool(remember)
                        st.success(f"Welcome back, {user[1]}!")
                        time.sleep(0.6)
                        st.experimental_rerun()
                    else:
                        st.error("Invalid email or password.")

    with tabs[1]:
        with st.form("register_form", clear_on_submit=False):
            rusername = st.text_input("Username", key="reg_username")
            remail = st.text_input("Email", key="reg_email")
            rpass = st.text_input("Password", type="password", key="reg_password")
            rsubmit = st.form_submit_button("Register")
            if rsubmit:
                if not rusername or not remail or not rpass:
                    st.warning("Please fill all fields.")
                else:
                    res = register_user(rusername.strip(), remail.strip(), rpass)
                    if res is True:
                        st.success("Registration successful — you can now log in.")
                    else:
                        st.error(res)

    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# ---------------------------------------------------------
# AFTER LOGIN: main app (normal UI)
# ---------------------------------------------------------
st.sidebar.success(f"👋 Logged in as {st.session_state.username}")
if st.sidebar.button("🚪 Logout"):
    st.session_state.logged_in = False
    st.session_state.user_id = None
    st.session_state.username = ""
    st.experimental_rerun()

# DB connection for app
conn = sqlite3.connect(DB_PATH)

# Main module selection
choice = st.sidebar.selectbox("Select Module", ["Database Overview", "Analytics", "Performance", "User Management", "Post Management"])

# small helper to draw a "glass" card area
def open_card(title=None):
    if title:
        st.markdown(f'<div style="background:rgba(255,255,255,0.03);padding:16px;border-radius:10px;margin-bottom:12px;"><h3 style="margin:6px 0;">{title}</h3>', unsafe_allow_html=True)
    else:
        st.markdown('<div style="background:rgba(255,255,255,0.03);padding:12px;border-radius:10px;margin-bottom:12px;">', unsafe_allow_html=True)

def close_card():
    st.markdown('</div>', unsafe_allow_html=True)

# ------------------------------
# Database Overview
# ------------------------------
if choice == "Database Overview":
    open_card("User & Post Overview")
    try:
        users_df = pd.read_sql_query("SELECT user_id, username, email, created_at FROM Users", conn)
    except Exception:
        users_df = pd.read_sql_query("SELECT user_id, username, email FROM Users", conn)
    posts_df = pd.read_sql_query("SELECT * FROM Posts", conn)
    st.write("### Users")
    st.dataframe(users_df)
    st.write("### Posts")
    st.dataframe(posts_df)
    close_card()

# ------------------------------
# Analytics
# ------------------------------
elif choice == "Analytics":
    open_card("Analytics")
    opt = st.selectbox("Choose Analysis", ["Most Active Users", "Top Influencers", "Trending Posts"])
    start_t = time.time()
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
    close_card()

# ------------------------------
# Performance
# ------------------------------
elif choice == "Performance":
    open_card("Performance")
    if st.button("Create Indexes for Optimization"):
        try:
            create_indexes(conn)
            st.success("Indexes created successfully.")
        except Exception as e:
            st.error(f"Index creation failed: {e}")
    if os.path.exists(os.path.join(BASE_DIR, "data", "performance_chart.png")):
        st.image(os.path.join(BASE_DIR, "data", "performance_chart.png"))
    else:
        st.info("No performance chart found in data/")
    close_card()

# ------------------------------
# User Management (Add/Edit/Delete/View)
# ------------------------------
elif choice == "User Management":
    open_card("User Management")
    tabs = st.tabs(["➕ Add User", "🖊️ Edit User", "❌ Delete User", "View Users"])

    # Add
    with tabs[0]:
        a_name = st.text_input("Username", key="um_add_name")
        a_email = st.text_input("Email", key="um_add_email")
        a_pw = st.text_input("Password", type="password", key="um_add_pw")
        if st.button("Add User"):
            if not a_name or not a_email or not a_pw:
                st.warning("Fill all fields.")
            else:
                res = register_user(a_name.strip(), a_email.strip(), a_pw)
                if res is True:
                    st.success("User added.")
                else:
                    st.error(res)

    # Edit
    with tabs[1]:
        try:
            df_users = pd.read_sql_query("SELECT user_id, username, email FROM Users", conn)
        except Exception:
            df_users = pd.DataFrame(columns=["user_id", "username", "email"])
        if not df_users.empty:
            sel = st.selectbox("Select user", df_users["user_id"], format_func=lambda x: df_users.loc[df_users["user_id"]==x,"username"].values[0])
            row = df_users[df_users["user_id"] == sel].iloc[0]
            new_name = st.text_input("Username", value=row["username"], key="um_edit_name")
            new_email = st.text_input("Email", value=row["email"], key="um_edit_email")
            new_pw = st.text_input("New password (leave empty to keep)", type="password", key="um_edit_pw")
            if st.button("Update User"):
                try:
                    if new_pw:
                        conn.execute("UPDATE Users SET username=?, email=?, password=? WHERE user_id=?", (new_name.strip(), new_email.strip(), hash_password(new_pw), sel))
                    else:
                        conn.execute("UPDATE Users SET username=?, email=? WHERE user_id=?", (new_name.strip(), new_email.strip(), sel))
                    conn.commit()
                    st.success("User updated.")
                except Exception as e:
                    st.error(f"Update failed: {e}")
        else:
            st.info("No users found.")

    # Delete
    with tabs[2]:
        try:
            df_users = pd.read_sql_query("SELECT user_id, username FROM Users", conn)
        except Exception:
            df_users = pd.DataFrame(columns=["user_id", "username"])
        if not df_users.empty:
            sel_del = st.selectbox("Select user to delete", df_users["user_id"], format_func=lambda x: df_users.loc[df_users["user_id"]==x,"username"].values[0])
            if st.button("Delete User"):
                try:
                    conn.execute("DELETE FROM Users WHERE user_id=?", (sel_del,))
                    conn.commit()
                    st.success("User deleted.")
                except Exception as e:
                    st.error(f"Deletion failed: {e}")
        else:
            st.info("No users available.")

    # View
    with tabs[3]:
        try:
            st.dataframe(pd.read_sql_query("SELECT user_id, username, email, created_at FROM Users", conn))
        except Exception:
            st.dataframe(pd.read_sql_query("SELECT user_id, username, email FROM Users", conn))
    close_card()

# ------------------------------
# Post Management (Add/Edit/Delete/View) with manual time entry option
# ------------------------------
elif choice == "Post Management":
    open_card("Post Management")
    tabs = st.tabs(["➕ Add Post", "🖊️ Edit Post", "❌ Delete Post", "View Posts"])

    with tabs[0]:
        users_df = pd.read_sql_query("SELECT user_id, username FROM Users", conn)
        if users_df.empty:
            st.info("No users found — add users first.")
        else:
            uid = st.selectbox("Select Author", users_df["user_id"], format_func=lambda x: users_df.loc[users_df["user_id"]==x,"username"].values[0])
            content = st.text_area("Content")
            likes = st.number_input("Likes", min_value=0, value=0)
            # manual date + time entry
            date_input = st.date_input("Date", datetime.now().date())
            time_input = st.text_input("Time (HH:MM:SS)", value=datetime.now().strftime("%H:%M:%S"))
            try:
                datetime.strptime(time_input, "%H:%M:%S")
                created_at = f"{date_input} {time_input}"
            except ValueError:
                created_at = None
                st.warning("Invalid time format. Use HH:MM:SS")

            if st.button("Add Post"):
                if not content or not created_at:
                    st.warning("Provide content and valid time.")
                else:
                    try:
                        conn.execute("INSERT INTO Posts (user_id, content, likes, created_at) VALUES (?, ?, ?, ?)",
                                     (uid, content, likes, created_at))
                        conn.commit()
                        st.success("Post added.")
                    except Exception as e:
                        st.error(f"Add failed: {e}")

    with tabs[1]:
        posts_df = pd.read_sql_query("SELECT post_id, content FROM Posts", conn)
        if posts_df.empty:
            st.info("No posts to edit.")
        else:
            pid = st.selectbox("Select post to edit", posts_df["post_id"], format_func=lambda x: posts_df.loc[posts_df["post_id"]==x,"content"].values[0])
            row = pd.read_sql_query("SELECT * FROM Posts WHERE post_id=?", conn, params=(pid,)).iloc[0]
            new_content = st.text_area("Content", value=row["content"])
            new_likes = st.number_input("Likes", min_value=0, value=int(row.get("likes", 0)))
            if st.button("Update Post"):
                try:
                    conn.execute("UPDATE Posts SET content=?, likes=? WHERE post_id=?", (new_content, new_likes, pid))
                    conn.commit()
                    st.success("Post updated.")
                except Exception as e:
                    st.error(f"Update failed: {e}")

    with tabs[2]:
        posts_df = pd.read_sql_query("SELECT post_id, content FROM Posts", conn)
        if posts_df.empty:
            st.info("No posts to delete.")
        else:
            pid_del = st.selectbox("Select post to delete", posts_df["post_id"], format_func=lambda x: posts_df.loc[posts_df["post_id"]==x,"content"].values[0])
            if st.button("Delete Post"):
                try:
                    conn.execute("DELETE FROM Posts WHERE post_id=?", (pid_del,))
                    conn.commit()
                    st.success("Post deleted.")
                except Exception as e:
                    st.error(f"Delete failed: {e}")

    with tabs[3]:
        try:
            st.dataframe(pd.read_sql_query("SELECT * FROM Posts ORDER BY created_at DESC", conn))
        except Exception:
            st.dataframe(pd.read_sql_query("SELECT * FROM Posts", conn))

    close_card()

# close DB connection
conn.close()
