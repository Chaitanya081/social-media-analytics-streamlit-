# app.py - Final full working code (clean UI, persistent users, user/post CRUD, analytics)
import streamlit as st
import sqlite3
import pandas as pd
import os
import tempfile
import hashlib
import time
from datetime import datetime

# Optional analytics helpers (if you implemented analytics/queries.py)
try:
    from analytics.queries import create_indexes
except Exception:
    def create_indexes(conn):
        # safe no-op fallback
        return

# -------------------------
# Config + DB paths
# -------------------------
st.set_page_config(page_title="Social Media Analytics Platform", layout="wide")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_SCHEMA_PATH = os.path.join(BASE_DIR, "db", "schema.sql")
DB_SAMPLE_PATH = os.path.join(BASE_DIR, "db", "sample_data.sql")

TEMP_DIR = tempfile.gettempdir()
DB_PATH = os.path.join(TEMP_DIR, "social_media.db")  # safe writable location

# -------------------------
# Utilities
# -------------------------
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def execute_script_if_file(cursor, path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            script = f.read()
        cursor.executescript(script)
        return True
    return False

# -------------------------
# Initialize DB (safe fallback if files missing)
# -------------------------
def ensure_database():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Try to load schema.sql if present; otherwise create minimal schema
    loaded = False
    try:
        loaded = execute_script_if_file(cur, DB_SCHEMA_PATH)
    except Exception:
        loaded = False

    if not loaded:
        # Minimal schema
        cur.execute("""
        CREATE TABLE IF NOT EXISTS Users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            password TEXT
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

    # Ensure password column exists (if schema came from older file)
    cur.execute("PRAGMA table_info(Users);")
    cols = [r[1] for r in cur.fetchall()]
    if "password" not in cols:
        try:
            cur.execute("ALTER TABLE Users ADD COLUMN password TEXT;")
        except Exception:
            pass

    # Seed sample data if no users present
    cur.execute("SELECT COUNT(*) FROM Users;")
    count = cur.fetchone()[0]
    if count == 0:
        # If there's sample_data.sql, use it; otherwise insert three named users required
        used_sample = False
        try:
            used_sample = execute_script_if_file(cur, DB_SAMPLE_PATH)
        except Exception:
            used_sample = False

        if not used_sample:
            # Insert exactly three users: Vishwa, Vigneshvar, G Chaitanya
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            users = [
                ("Vishwa", "vishwa123@gmail.com", hash_password("vishwa123"), now),
                ("Vigneshvar", "vigneshvar123@gmail.com", hash_password("vignesh123"), now),
                ("G Chaitanya", "chaithanya06gutti@gmail.com", hash_password("chaitanya123"), now),
            ]
            cur.executemany("INSERT INTO Users (username, email, password, created_at) VALUES (?, ?, ?, ?);", users)

            # Insert a couple of sample posts showing the author mapping
            cur.execute("INSERT INTO Posts (user_id, content, likes, created_at) VALUES (?, ?, ?, ?);",
                        (1, "Welcome to the Social Media Analytics demo by Vishwa.", 5, now))
            cur.execute("INSERT INTO Posts (user_id, content, likes, created_at) VALUES (?, ?, ?, ?);",
                        (2, "This is a sample post by Vigneshvar.", 2, now))
    conn.commit()
    conn.close()

ensure_database()

# -------------------------
# Auth helpers
# -------------------------
def verify_user(email: str, password: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    h = hash_password(password)
    cur.execute("SELECT user_id, username, email FROM Users WHERE email=? AND password=?", (email, h))
    user = cur.fetchone()
    conn.close()
    return user  # None or (user_id, username, email)

def register_user(username: str, email: str, password: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM Users WHERE email=?", (email,))
    if cur.fetchone():
        conn.close()
        return "Email already registered."
    h = hash_password(password)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        cur.execute("INSERT INTO Users (username, email, password, created_at) VALUES (?, ?, ?, ?);",
                    (username, email, h, now))
        conn.commit()
    except Exception as e:
        conn.close()
        return str(e)
    conn.close()
    return True

# -------------------------
# Session state init
# -------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user" not in st.session_state:
    st.session_state.user = None  # (user_id, username, email)

# -------------------------
# Login / Register UI (clean, simple; no background)
# -------------------------
if not st.session_state.logged_in:
    st.title("📊 Social Media Analytics Platform")
    st.write("Please log in to continue (registered users persist).")

    tab1, tab2 = st.tabs(["🔑 Login", "🆕 Register"])

    with tab1:
        login_email = st.text_input("Email", key="login_email")
        login_password = st.text_input("Password", type="password", key="login_password")
        if st.button("Login"):
            if not login_email or not login_password:
                st.warning("Fill both email and password.")
            else:
                user = verify_user(login_email.strip(), login_password)
                if user:
                    st.session_state.logged_in = True
                    st.session_state.user = user
                    st.success(f"Welcome, {user[1]}!")
                    st.experimental_rerun()
                else:
                    st.error("Invalid email or password. If you just registered, use the registered password.")

    with tab2:
        reg_username = st.text_input("Username", key="reg_username")
        reg_email = st.text_input("Email", key="reg_email")
        reg_password = st.text_input("Password", type="password", key="reg_password")
        if st.button("Register"):
            if not reg_username or not reg_email or not reg_password:
                st.warning("Fill all fields.")
            else:
                res = register_user(reg_username.strip(), reg_email.strip(), reg_password)
                if res is True:
                    st.success("Registration successful — now login with your credentials.")
                else:
                    st.error(res)

    st.stop()

# -------------------------
# After login: main app
# -------------------------
user_id, username, user_email = st.session_state.user
st.sidebar.success(f"👋 {username}")
if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.session_state.user = None
    st.experimental_rerun()

# Connect DB
conn = sqlite3.connect(DB_PATH)

# Sidebar modules
module = st.sidebar.selectbox("Select Module",
                              ["Database Overview", "Analytics", "Performance", "User Management", "Post Management"])

# -------------------------
# Module: Database Overview
# -------------------------
if module == "Database Overview":
    st.header("User & Post Overview")
    users_df = pd.read_sql_query("SELECT user_id, username, email, created_at FROM Users ORDER BY user_id;", conn)
    posts_df = pd.read_sql_query("""
        SELECT p.post_id, p.content, p.likes, p.created_at, u.username AS author
        FROM Posts p LEFT JOIN Users u ON p.user_id = u.user_id
        ORDER BY p.created_at DESC
    """, conn)

    st.subheader("Users")
    st.dataframe(users_df)

    st.subheader("Posts (with author)")
    st.dataframe(posts_df)

# -------------------------
# Module: Analytics
# -------------------------
elif module == "Analytics":
    st.header("Analytics")
    choice = st.selectbox("Choose", ["Most Active Users", "Top Influencers", "Trending Posts"])

    start = time.time()
    try:
        if choice == "Most Active Users":
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
            if not df.empty:
                st.bar_chart(df.set_index("username"))
            else:
                st.info("No activity found.")
        elif choice == "Top Influencers":
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
                st.info("No relationships found.")
        elif choice == "Trending Posts":
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
    st.info(f"Query time: {round(time.time() - start, 4)} sec")

# -------------------------
# Module: Performance
# -------------------------
elif module == "Performance":
    st.header("Performance & Indexing")
    if st.button("Create Indexes"):
        try:
            create_indexes(conn)
            st.success("Indexes created (or attempted).")
        except Exception as e:
            st.error(f"Indexing error: {e}")
    if os.path.exists(os.path.join(BASE_DIR, "data", "performance_chart.png")):
        st.image(os.path.join(BASE_DIR, "data", "performance_chart.png"))
    else:
        st.info("No performance chart found (optional).")

# -------------------------
# Module: User Management
# -------------------------
elif module == "User Management":
    st.header("User Management")

    tab_add, tab_edit, tab_delete, tab_view = st.tabs(["➕ Add User", "🖊️ Edit User", "❌ Delete User", "View Users"])

    with tab_add:
        un = st.text_input("Username", key="um_add_un")
        ue = st.text_input("Email", key="um_add_em")
        up = st.text_input("Password", type="password", key="um_add_pw")
        if st.button("Add User"):
            if not un or not ue or not up:
                st.warning("Fill all fields.")
            else:
                r = register_user(un.strip(), ue.strip(), up)
                if r is True:
                    st.success("User added.")
                else:
                    st.error(r)

    with tab_edit:
        df_users = pd.read_sql_query("SELECT user_id, username, email FROM Users ORDER BY user_id", conn)
        if df_users.empty:
            st.info("No users.")
        else:
            sel = st.selectbox("Select user to edit", df_users["user_id"],
                               format_func=lambda x: df_users[df_users["user_id"] == x]["username"].values[0])
            row = df_users[df_users["user_id"] == sel].iloc[0]
            new_un = st.text_input("Username", value=row["username"], key="um_edit_un")
            new_em = st.text_input("Email", value=row["email"], key="um_edit_em")
            new_pw = st.text_input("New Password (leave blank to keep)", type="password", key="um_edit_pw")
            if st.button("Update User"):
                try:
                    if new_pw:
                        conn.execute("UPDATE Users SET username=?, email=?, password=? WHERE user_id=?",
                                     (new_un.strip(), new_em.strip(), hash_password(new_pw), sel))
                    else:
                        conn.execute("UPDATE Users SET username=?, email=? WHERE user_id=?",
                                     (new_un.strip(), new_em.strip(), sel))
                    conn.commit()
                    st.success("User updated.")
                except Exception as e:
                    st.error(f"Update failed: {e}")

    with tab_delete:
        df_users = pd.read_sql_query("SELECT user_id, username FROM Users ORDER BY user_id", conn)
        if df_users.empty:
            st.info("No users.")
        else:
            sel = st.selectbox("Select user to delete", df_users["user_id"],
                               format_func=lambda x: df_users[df_users["user_id"] == x]["username"].values[0])
            if st.button("Delete User"):
                try:
                    conn.execute("DELETE FROM Users WHERE user_id=?", (sel,))
                    conn.commit()
                    st.success("User deleted.")
                except Exception as e:
                    st.error(f"Delete failed: {e}")

    with tab_view:
        st.dataframe(pd.read_sql_query("SELECT user_id, username, email, created_at FROM Users ORDER BY user_id", conn))

# -------------------------
# Module: Post Management
# -------------------------
elif module == "Post Management":
    st.header("Post Management")

    tab_add, tab_edit, tab_delete, tab_view = st.tabs(["➕ Add Post", "🖊️ Edit Post", "❌ Delete Post", "View Posts"])

    with tab_add:
        users_df = pd.read_sql_query("SELECT user_id, username FROM Users ORDER BY user_id", conn)
        if users_df.empty:
            st.info("No users - add users first.")
        else:
            sel_user = st.selectbox("Select author", users_df["user_id"],
                                    format_func=lambda x: users_df[users_df["user_id"] == x]["username"].values[0])
            content = st.text_area("Content")
            likes = st.number_input("Likes", min_value=0, value=0)
            date_val = st.date_input("Date", datetime.now().date())
            time_str = st.text_input("Time (HH:MM:SS)", value=datetime.now().strftime("%H:%M:%S"))
            try:
                datetime.strptime(time_str, "%H:%M:%S")
                created_at = f"{date_val} {time_str}"
            except ValueError:
                created_at = None

            if st.button("Add Post"):
                if not content or not created_at:
                    st.warning("Provide content and valid time.")
                else:
                    try:
                        conn.execute("INSERT INTO Posts (user_id, content, likes, created_at) VALUES (?, ?, ?, ?)",
                                     (sel_user, content, likes, created_at))
                        conn.commit()
                        st.success("Post added.")
                    except Exception as e:
                        st.error(f"Add failed: {e}")

    with tab_edit:
        posts = pd.read_sql_query("SELECT post_id, content FROM Posts ORDER BY created_at DESC", conn)
        if posts.empty:
            st.info("No posts.")
        else:
            sel_post = st.selectbox("Select post to edit", posts["post_id"],
                                    format_func=lambda x: posts[posts["post_id"] == x]["content"].values[0])
            row = pd.read_sql_query("SELECT * FROM Posts WHERE post_id=?", conn, params=(sel_post,)).iloc[0]
            new_content = st.text_area("Content", value=row["content"])
            new_likes = st.number_input("Likes", min_value=0, value=int(row.get("likes", 0)))
            if st.button("Update Post"):
                try:
                    conn.execute("UPDATE Posts SET content=?, likes=? WHERE post_id=?", (new_content, new_likes, sel_post))
                    conn.commit()
                    st.success("Post updated.")
                except Exception as e:
                    st.error(f"Update failed: {e}")

    with tab_delete:
        posts = pd.read_sql_query("SELECT post_id, content FROM Posts ORDER BY created_at DESC", conn)
        if posts.empty:
            st.info("No posts.")
        else:
            sel_post = st.selectbox("Select post to delete", posts["post_id"],
                                    format_func=lambda x: posts[posts["post_id"] == x]["content"].values[0])
            if st.button("Delete Post"):
                try:
                    conn.execute("DELETE FROM Posts WHERE post_id=?", (sel_post,))
                    conn.commit()
                    st.success("Post deleted.")
                except Exception as e:
                    st.error(f"Delete failed: {e}")

    with tab_view:
        df = pd.read_sql_query("""
            SELECT p.post_id, p.content, p.likes, p.created_at, u.username AS author
            FROM Posts p LEFT JOIN Users u ON p.user_id = u.user_id
            ORDER BY p.created_at DESC
        """, conn)
        st.dataframe(df)

# Close DB
conn.close()
