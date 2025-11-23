# app.py - final updated code (Version A: hero banner + glass login + full functionality)
import streamlit as st
import sqlite3
import pandas as pd
import os
import tempfile
import hashlib
import time
from datetime import datetime

# ---------------------------
# Config / Paths
# ---------------------------
st.set_page_config(page_title="Social Media Analytics Platform", layout="wide")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(BASE_DIR, "db")
DB_SCHEMA_PATH = os.path.join(DB_DIR, "schema.sql")
DB_SAMPLE_PATH = os.path.join(DB_DIR, "sample_data.sql")
BANNER_PATH = os.path.join(BASE_DIR, "data", "SocialMedia1.png")

# Use a temp DB path (works on Streamlit Cloud). You can change to a repo path if desired.
TEMP_DIR = tempfile.gettempdir()
DB_PATH = os.path.join(TEMP_DIR, "social_media.db")

# ---------------------------
# Utilities
# ---------------------------
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def _exec_script_if_exists(cur, path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            cur.executescript(f.read())
        return True
    return False

# ---------------------------
# Ensure DB + Schema
# ---------------------------
def ensure_database():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # If schema file exists use it, otherwise create fallback schema
    if not _exec_script_if_exists(cur, DB_SCHEMA_PATH):
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

    # If sample_data.sql exists and Users empty, load it; otherwise insert minimal sample users if empty
    cur.execute("SELECT COUNT(*) FROM Users;")
    cnt = cur.fetchone()[0]
    if cnt == 0:
        if not _exec_script_if_exists(cur, DB_SAMPLE_PATH):
            # fallback sample data
            cur.executescript(f"""
            INSERT INTO Users (username, email, password, created_at) VALUES
              ('Alice', 'alice@example.com', '{hash_password("alice123")}', datetime('now')),
              ('Bob', 'bob@example.com', '{hash_password("bob123")}', datetime('now')),
              ('Charlie', 'charlie@example.com', '{hash_password("charlie123")}', datetime('now')),
              ('G Chaitanya', 'chaithanya06gutti@gmail.com', '{hash_password("project123")}', datetime('now'));
            INSERT INTO Posts (user_id, content, likes, created_at) VALUES
              (1, 'Hello World!', 5, '2024-01-15 10:22:00'),
              (2, 'My first post!', 12, '2024-02-20 15:45:00'),
              (3, 'Nice weather today!', 7, '2024-03-01 09:10:00'),
              (4, 'How to deploy an app', 10000, datetime('now'));
            """)
    conn.commit()
    conn.close()

ensure_database()

# ---------------------------
# DB helpers
# ---------------------------
def get_conn():
    return sqlite3.connect(DB_PATH)

def verify_user(email, password):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT user_id, username, email FROM Users WHERE email=? AND password=?", (email, hash_password(password)))
    row = cur.fetchone()
    conn.close()
    return row  # None or (user_id, username, email)

def register_user(username, email, password):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO Users (username, email, password, created_at) VALUES (?, ?, ?, ?)",
                    (username, email, hash_password(password), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        return True, None
    except sqlite3.IntegrityError as e:
        return False, "Email already registered."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

# ---------------------------
# Styling - hero + glass card
# ---------------------------
HERO_CSS = f"""
<style>
.app-hero {{
  width:100%;
  height:360px;
  border-radius:12px;
  background-image: url("file://{BANNER_PATH}") ;
  background-size: cover;
  background-position: center;
  position: relative;
  margin-bottom: 26px;
  box-shadow: 0 10px 40px rgba(0,0,0,0.7);
  overflow: hidden;
}}
.hero-overlay {{
  position: absolute;
  inset: 0;
  background: linear-gradient(to bottom, rgba(0,0,0,0.32), rgba(0,0,0,0.46));
}}
.hero-card {{
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%,-50%);
  width: min(980px, 92%);
  padding: 22px 28px;
  border-radius: 12px;
  background: rgba(255,255,255,0.06);
  backdrop-filter: blur(6px) saturate(120%);
  border: 1px solid rgba(255,255,255,0.06);
  box-shadow: 0 12px 30px rgba(0,0,0,0.6);
  color: #fff;
  text-align:center;
}}
.hero-title {{
  font-size: 36px;
  font-weight: 800;
  margin-bottom: 6px;
  color: #fff;
  text-shadow: 2px 6px 16px rgba(0,0,0,0.6);
}}
.hero-sub {{
  color: rgba(255,255,255,0.92);
  margin-bottom: 12px;
}}

.form-inner {{
  padding-top: 6px;
  padding-bottom: 6px;
}}

.stTextInput>div>div>input, .stTextArea>div>div>textarea {{
  background: rgba(0,0,0,0.45) !important;
  border-radius: 8px !important;
  color: #fff !important;
}}
.small-glass-card {{
  background: rgba(255,255,255,0.035);
  border-radius: 10px;
  padding: 14px;
  box-shadow: 0 6px 18px rgba(0,0,0,0.45);
  border: 1px solid rgba(255,255,255,0.03);
  color: #fff;
  margin-bottom: 18px;
}}
</style>
"""

st.markdown(HERO_CSS, unsafe_allow_html=True)

# ---------------------------
# Login / Register (Hero)
# ---------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "user_id" not in st.session_state:
    st.session_state.user_id = None

# Show hero (use fallback if image missing: solid background)
if os.path.exists(BANNER_PATH):
    st.markdown(f"""
    <div class="app-hero">
      <div class="hero-overlay"></div>
      <div class="hero-card">
        <div class="hero-title">SOCIAL MEDIA ANALYTICS PLATFORM</div>
        <div class="hero-sub">Secure analytics — sign in to continue</div>
        <div class="form-inner"></div>
      </div>
    </div>
    """, unsafe_allow_html=True)
else:
    # simple top heading if no image
    st.markdown("<div style='padding:20px;border-radius:8px;margin-bottom:18px;background:#111;color:#fff'><h1 style='margin:0'>SOCIAL MEDIA ANALYTICS PLATFORM</h1><p style='margin:0.2rem 0 0'>Secure analytics — sign in to continue</p></div>", unsafe_allow_html=True)

# If not logged in, render login/register tabs below hero
if not st.session_state.logged_in:
    tabs = st.tabs(["🔑 Login", "🆕 Register"])
    with tabs[0]:
        with st.form("login_form", clear_on_submit=False):
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Password", type="password", key="login_password")
            remember = st.checkbox("Remember me (session only)")
            submitted = st.form_submit_button("Sign In")
            if submitted:
                if not email or not password:
                    st.warning("Please fill both email and password.")
                else:
                    user = verify_user(email.strip(), password)
                    if user:
                        st.session_state.logged_in = True
                        st.session_state.user_id = user[0]
                        st.session_state.username = user[1]
                        if remember:
                            st.session_state["remembered_user"] = (email.strip(), hash_password(password))
                        st.success(f"Welcome back, {st.session_state.username}!")
                        time.sleep(0.2)
                        st.experimental_rerun()
                    else:
                        st.error("Invalid credentials. If you registered earlier, ensure your password is correct.")
    with tabs[1]:
        with st.form("register_form", clear_on_submit=True):
            new_username = st.text_input("New Username", key="reg_username")
            new_email = st.text_input("New Email", key="reg_email")
            new_password = st.text_input("New Password", type="password", key="reg_password")
            reg_sub = st.form_submit_button("Register")
            if reg_sub:
                if not new_username or not new_email or not new_password:
                    st.warning("Please fill all fields.")
                else:
                    ok, msg = register_user(new_username.strip(), new_email.strip(), new_password)
                    if ok:
                        st.success("Registration successful — you can sign in now.")
                    else:
                        st.error(msg)
    st.stop()  # require login to continue

# ---------------------------
# After login: Sidebar + Navigation
# ---------------------------
with st.sidebar:
    st.markdown('<div class="small-glass-card">', unsafe_allow_html=True)
    st.markdown(f"**👋 Logged in as**  \n**{st.session_state.username}**", unsafe_allow_html=True)
    if st.button("🚪 Logout"):
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.session_state.user_id = None
        # clear remembered user
        if "remembered_user" in st.session_state:
            del st.session_state["remembered_user"]
        st.experimental_rerun()
    st.markdown('</div>', unsafe_allow_html=True)

module = st.sidebar.selectbox("Select Module", ["Database Overview", "Analytics", "Performance", "User Management", "Post Management"])

# DB connection
conn = get_conn()

# ---------------------------
# MODULES
# ---------------------------

# Database Overview
if module == "Database Overview":
    st.header("User and Post Overview")
    try:
        users_df = pd.read_sql_query("SELECT user_id, username, email, created_at FROM Users ORDER BY user_id", conn)
        # show author username in posts table by join
        posts_df = pd.read_sql_query("""
            SELECT p.post_id, p.user_id, u.username AS author, p.content, p.likes, p.created_at
            FROM Posts p LEFT JOIN Users u ON p.user_id = u.user_id
            ORDER BY p.created_at DESC
        """, conn)
        st.subheader("👥 Users Table")
        st.dataframe(users_df)
        st.subheader("📝 Posts Table")
        st.dataframe(posts_df)
    except Exception as e:
        st.error(f"Failed to load tables: {e}")

# Analytics
elif module == "Analytics":
    st.header("Analytics")
    option = st.selectbox("Choose Analysis", ["Most Active Users", "Top Influencers", "Trending Posts"])
    start_t = time.time()
    try:
        if option == "Most Active Users":
            q = """
            SELECT u.username,
                (IFNULL(posts.cnt,0) + IFNULL(comments.cnt,0)) AS total_activity
            FROM Users u
            LEFT JOIN (SELECT user_id, COUNT(*) AS cnt FROM Posts GROUP BY user_id) posts ON posts.user_id = u.user_id
            LEFT JOIN (SELECT user_id, COUNT(*) AS cnt FROM Comments GROUP BY user_id) comments ON comments.user_id = u.user_id
            ORDER BY total_activity DESC LIMIT 10;
            """
            df = pd.read_sql_query(q, conn)
            if not df.empty:
                st.bar_chart(df.set_index("username"))
            else:
                st.info("No activity data.")
        elif option == "Top Influencers":
            q = """
            SELECT u.username, COUNT(r.follower_id) AS followers
            FROM Users u LEFT JOIN Relationships r ON r.following_id = u.user_id
            GROUP BY u.username ORDER BY followers DESC LIMIT 10;
            """
            df = pd.read_sql_query(q, conn)
            if not df.empty:
                st.bar_chart(df.set_index("username"))
            else:
                st.info("No relationship data.")
        elif option == "Trending Posts":
            q = """
            SELECT p.post_id, u.username as author, p.content, p.likes + IFNULL(c.cnt,0) AS engagement_score
            FROM Posts p
            LEFT JOIN Users u ON p.user_id = u.user_id
            LEFT JOIN (SELECT post_id, COUNT(*) AS cnt FROM Comments GROUP BY post_id) c ON c.post_id = p.post_id
            ORDER BY engagement_score DESC LIMIT 10;
            """
            df = pd.read_sql_query(q, conn)
            if not df.empty:
                st.dataframe(df)
            else:
                st.info("No trending posts.")
        st.info(f"Query time: {round(time.time() - start_t, 4)}s")
    except Exception as e:
        st.error(f"Analytics error: {e}")

# Performance
elif module == "Performance":
    st.header("Performance")
    try:
        from analytics.queries import create_indexes  # optional import
        if st.button("Create Indexes for Optimization"):
            try:
                create_indexes(conn)
                st.success("Indexes created.")
            except Exception as e:
                st.error(f"Index creation failed: {e}")
    except Exception:
        st.info("Index helper not available. Place analytics/queries.py to enable index creation.")
    perf_img = os.path.join(BASE_DIR, "data", "performance_chart.png")
    if os.path.exists(perf_img):
        st.image(perf_img, use_column_width=True)
    else:
        st.info("No performance chart available in data/")

# User Management
elif module == "User Management":
    st.header("Manage Users")
    tab_add, tab_edit, tab_delete, tab_view = st.tabs(["➕ Add User", "🖊️ Edit User", "❌ Delete User", "View Users"])

    with tab_add:
        with st.form("add_user_form"):
            uname = st.text_input("Username", key="um_add_un")
            uemail = st.text_input("Email", key="um_add_em")
            upw = st.text_input("Password", type="password", key="um_add_pw")
            added = st.form_submit_button("Add User")
            if added:
                if not uname or not uemail or not upw:
                    st.warning("Fill all fields.")
                else:
                    ok, msg = register_user(uname.strip(), uemail.strip(), upw)
                    if ok:
                        st.success("User added.")
                    else:
                        st.error(msg)

    with tab_edit:
        df_users = pd.read_sql_query("SELECT user_id, username, email FROM Users ORDER BY user_id", conn)
        if not df_users.empty:
            uid = st.selectbox("Select user", df_users["user_id"], format_func=lambda x: df_users.loc[df_users["user_id"]==x,"username"].values[0], key="um_edit_select")
            row = df_users[df_users["user_id"]==uid].iloc[0]
            new_un = st.text_input("Username", value=row["username"], key="um_edit_un")
            new_em = st.text_input("Email", value=row["email"], key="um_edit_em")
            new_pw = st.text_input("New password (leave blank to keep)", type="password", key="um_edit_pw")
            if st.button("Update User", key="um_edit_btn"):
                try:
                    cur = conn.cursor()
                    if new_pw:
                        cur.execute("UPDATE Users SET username=?, email=?, password=? WHERE user_id=?", (new_un.strip(), new_em.strip(), hash_password(new_pw), uid))
                    else:
                        cur.execute("UPDATE Users SET username=?, email=? WHERE user_id=?", (new_un.strip(), new_em.strip(), uid))
                    conn.commit()
                    st.success("User updated.")
                except Exception as e:
                    st.error(f"Update failed: {e}")
        else:
            st.info("No users found.")

    with tab_delete:
        df_users2 = pd.read_sql_query("SELECT user_id, username FROM Users ORDER BY user_id", conn)
        if not df_users2.empty:
            uid_del = st.selectbox("Select user to delete", df_users2["user_id"], format_func=lambda x: df_users2.loc[df_users2["user_id"]==x,"username"].values[0], key="um_del_select")
            if st.button("Delete User", key="um_del_btn"):
                try:
                    conn.execute("DELETE FROM Users WHERE user_id=?", (uid_del,))
                    conn.commit()
                    st.success("User deleted.")
                except Exception as e:
                    st.error(f"Delete failed: {e}")
        else:
            st.info("No users available.")

    with tab_view:
        df_all = pd.read_sql_query("SELECT user_id, username, email, created_at FROM Users ORDER BY user_id", conn)
        st.dataframe(df_all)

# Post Management
elif module == "Post Management":
    st.header("Manage Posts")
    tab1, tab2, tab3 = st.tabs(["➕ Add Post", "🖊️ Edit Post", "❌ Delete Post"])

    with tab1:
        users_df = pd.read_sql_query("SELECT user_id, username FROM Users ORDER BY user_id", conn)
        if users_df.empty:
            st.info("No users found - add users first.")
        else:
            uid = st.selectbox("Select User", users_df["user_id"], format_func=lambda x: users_df.loc[users_df["user_id"]==x,"username"].values[0], key="pm_add_user")
            content = st.text_area("Content", key="pm_add_content")
            likes = st.number_input("Likes", min_value=0, value=0, key="pm_add_likes")
            date_input = st.date_input("Date", datetime.now().date(), key="pm_add_date")
            time_str = st.text_input("Time (HH:MM:SS)", value=datetime.now().strftime("%H:%M:%S"), key="pm_add_time")
            try:
                # validate time
                datetime.strptime(time_str, "%H:%M:%S")
                created_at = f"{date_input} {time_str}"
            except Exception:
                created_at = None
            if st.button("Add Post", key="pm_add_btn"):
                if content and created_at:
                    try:
                        conn.execute("INSERT INTO Posts (user_id, content, likes, created_at) VALUES (?, ?, ?, ?)", (uid, content, likes, created_at))
                        conn.commit()
                        st.success("Post added.")
                    except Exception as e:
                        st.error(f"Add failed: {e}")
                else:
                    st.warning("Provide content and valid time.")

            st.write("### Existing Posts")
            df_posts = pd.read_sql_query("""
               SELECT p.post_id, p.content, p.likes, p.created_at, u.username as author
               FROM Posts p LEFT JOIN Users u ON p.user_id = u.user_id
               ORDER BY p.created_at DESC
            """, conn)
            st.dataframe(df_posts)

    with tab2:
        posts_df = pd.read_sql_query("SELECT post_id, content FROM Posts ORDER BY post_id", conn)
        if posts_df.empty:
            st.info("No posts to edit.")
        else:
            pid = st.selectbox("Select post to edit", posts_df["post_id"], format_func=lambda x: posts_df.loc[posts_df["post_id"]==x,"content"].values[0], key="pm_edit_select")
            row = pd.read_sql_query("SELECT * FROM Posts WHERE post_id=?", conn, params=(pid,)).iloc[0]
            new_content = st.text_area("Content", value=row["content"], key="pm_edit_content")
            new_likes = st.number_input("Likes", min_value=0, value=int(row.get("likes", 0)), key="pm_edit_likes")
            if st.button("Update Post", key="pm_edit_btn"):
                try:
                    conn.execute("UPDATE Posts SET content=?, likes=? WHERE post_id=?", (new_content, new_likes, pid))
                    conn.commit()
                    st.success("Post updated.")
                except Exception as e:
                    st.error(f"Update failed: {e}")

    with tab3:
        posts_df2 = pd.read_sql_query("SELECT post_id, content FROM Posts ORDER BY post_id", conn)
        if posts_df2.empty:
            st.info("No posts to delete.")
        else:
            pid_del = st.selectbox("Select post to delete", posts_df2["post_id"], format_func=lambda x: posts_df2.loc[posts_df2["post_id"]==x,"content"].values[0], key="pm_del_select")
            if st.button("Delete Post", key="pm_del_btn"):
                try:
                    conn.execute("DELETE FROM Posts WHERE post_id=?", (pid_del,))
                    conn.commit()
                    st.success("Post deleted.")
                except Exception as e:
                    st.error(f"Delete failed: {e}")

# ---------------------------
# Close DB
# ---------------------------
conn.close()
