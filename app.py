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
    tabs = st.tabs(["➕ Add User", "🖊️ Edit User", "❌ Delete User", "👥 View Users", "🔗 Manage Relationships"])

    # Add User
    with tabs[0]:
        st.subheader("Add New User")
        with st.form("add_user_form", clear_on_submit=True):
            a_name = st.text_input("Username", key="um_add_name")
            a_email = st.text_input("Email", key="um_add_email")
            a_pw = st.text_input("Password", type="password", key="um_add_pw")
            submitted = st.form_submit_button("Add User")
            if submitted:
                if not a_name or not a_email or not a_pw:
                    st.warning("Please fill all fields.")
                else:
                    res = register_user(a_name.strip(), a_email.strip(), a_pw)
                    if res is True:
                        st.success("User added successfully!")
                        st.experimental_rerun()
                    else:
                        st.error(res)

    # Edit User
    with tabs[1]:
        st.subheader("Edit Existing User")
        try:
            df_users = pd.read_sql_query("SELECT user_id, username, email FROM Users", conn)
        except Exception:
            df_users = pd.DataFrame(columns=["user_id", "username", "email"])
        
        if not df_users.empty:
            sel = st.selectbox("Select user", df_users["user_id"], 
                              format_func=lambda x: f"{df_users.loc[df_users['user_id']==x,'username'].values[0]} (ID: {x})",
                              key="edit_user_select")
            row = df_users[df_users["user_id"] == sel].iloc[0]
            
            new_name = st.text_input("Username", value=row["username"], key="um_edit_name")
            new_email = st.text_input("Email", value=row["email"], key="um_edit_email")
            new_pw = st.text_input("New password (leave empty to keep current)", type="password", key="um_edit_pw")
            
            if st.button("Update User", key="update_user_btn"):
                try:
                    if new_pw:
                        conn.execute("UPDATE Users SET username=?, email=?, password=? WHERE user_id=?", 
                                    (new_name.strip(), new_email.strip(), hash_password(new_pw), sel))
                    else:
                        conn.execute("UPDATE Users SET username=?, email=? WHERE user_id=?", 
                                    (new_name.strip(), new_email.strip(), sel))
                    conn.commit()
                    st.success("User updated successfully!")
                    st.experimental_rerun()
                except Exception as e:
                    st.error(f"Update failed: {e}")
        else:
            st.info("No users found in the database.")

    # Delete User
    with tabs[2]:
        st.subheader("Delete User")
        try:
            df_users = pd.read_sql_query("SELECT user_id, username FROM Users", conn)
        except Exception:
            df_users = pd.DataFrame(columns=["user_id", "username"])
        
        if not df_users.empty:
            sel_del = st.selectbox("Select user to delete", df_users["user_id"], 
                                  format_func=lambda x: f"{df_users.loc[df_users['user_id']==x,'username'].values[0]} (ID: {x})",
                                  key="delete_user_select")
            
            # Show user details before deletion
            if sel_del:
                user_details = df_users[df_users["user_id"] == sel_del].iloc[0]
                st.warning(f"You are about to delete user: **{user_details['username']}** (ID: {sel_del})")
                
                # Check if user has posts
                post_count = pd.read_sql_query("SELECT COUNT(*) as count FROM Posts WHERE user_id=?", conn, params=(sel_del,)).iloc[0]['count']
                if post_count > 0:
                    st.warning(f"This user has {post_count} post(s) that will also be deleted!")
                
                if st.button("Confirm Delete", key="confirm_delete_btn"):
                    try:
                        # Delete user's posts first (to maintain referential integrity)
                        conn.execute("DELETE FROM Posts WHERE user_id=?", (sel_del,))
                        # Delete user's comments
                        conn.execute("DELETE FROM Comments WHERE user_id=?", (sel_del,))
                        # Delete user's relationships
                        conn.execute("DELETE FROM Relationships WHERE follower_id=? OR following_id=?", (sel_del, sel_del))
                        # Finally delete the user
                        conn.execute("DELETE FROM Users WHERE user_id=?", (sel_del,))
                        conn.commit()
                        st.success("User and associated data deleted successfully!")
                        st.experimental_rerun()
                    except Exception as e:
                        st.error(f"Deletion failed: {e}")
        else:
            st.info("No users available for deletion.")

    # View Users
    with tabs[3]:
        st.subheader("All Users")
        try:
            users_df = pd.read_sql_query("""
                SELECT u.user_id, u.username, u.email, u.created_at, 
                       COUNT(DISTINCT p.post_id) as post_count,
                       COUNT(DISTINCT r.following_id) as followers_count
                FROM Users u
                LEFT JOIN Posts p ON u.user_id = p.user_id
                LEFT JOIN Relationships r ON u.user_id = r.following_id
                GROUP BY u.user_id
                ORDER BY u.user_id
            """, conn)
            
            if not users_df.empty:
                st.dataframe(users_df, use_container_width=True)
                
                # Statistics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Users", len(users_df))
                with col2:
                    st.metric("Total Posts", users_df['post_count'].sum())
                with col3:
                    st.metric("Most Active User", 
                             users_df.loc[users_df['post_count'].idxmax(), 'username'] if users_df['post_count'].max() > 0 else "N/A")
            else:
                st.info("No users found in the database.")
        except Exception as e:
            st.error(f"Error loading users: {e}")

    # Manage Relationships
    with tabs[4]:
        st.subheader("Manage User Relationships")
        
        # Get all users
        users_df = pd.read_sql_query("SELECT user_id, username FROM Users", conn)
        
        if len(users_df) >= 2:
            col1, col2 = st.columns(2)
            
            with col1:
                follower = st.selectbox("Follower", users_df["user_id"], 
                                       format_func=lambda x: f"{users_df.loc[users_df['user_id']==x,'username'].values[0]} (ID: {x})",
                                       key="follower_select")
            
            with col2:
                following = st.selectbox("Following", users_df["user_id"], 
                                        format_func=lambda x: f"{users_df.loc[users_df['user_id']==x,'username'].values[0]} (ID: {x})",
                                        key="following_select")
            
            if st.button("Create Relationship", key="create_relation_btn"):
                if follower == following:
                    st.error("A user cannot follow themselves!")
                else:
                    try:
                        # Check if relationship already exists
                        existing = pd.read_sql_query(
                            "SELECT 1 FROM Relationships WHERE follower_id=? AND following_id=?", 
                            conn, params=(follower, following)
                        )
                        
                        if not existing.empty:
                            st.warning("This relationship already exists!")
                        else:
                            conn.execute("INSERT INTO Relationships (follower_id, following_id) VALUES (?, ?)", 
                                        (follower, following))
                            conn.commit()
                            st.success("Relationship created successfully!")
                    except Exception as e:
                        st.error(f"Failed to create relationship: {e}")
            
            # Show existing relationships
            st.subheader("Existing Relationships")
            relationships_df = pd.read_sql_query("""
                SELECT r.follower_id, f.username as follower_name, 
                       r.following_id, fl.username as following_name
                FROM Relationships r
                JOIN Users f ON r.follower_id = f.user_id
                JOIN Users fl ON r.following_id = fl.user_id
                ORDER BY f.username
            """, conn)
            
            if not relationships_df.empty:
                st.dataframe(relationships_df, use_container_width=True)
                
                # Option to delete a relationship
                rel_to_delete = st.selectbox("Select relationship to delete", 
                                           range(len(relationships_df)),
                                           format_func=lambda x: f"{relationships_df.iloc[x]['follower_name']} → {relationships_df.iloc[x]['following_name']}",
                                           key="delete_rel_select")
                
                if st.button("Delete Relationship", key="delete_rel_btn"):
                    try:
                        rel = relationships_df.iloc[rel_to_delete]
                        conn.execute("DELETE FROM Relationships WHERE follower_id=? AND following_id=?", 
                                    (rel['follower_id'], rel['following_id']))
                        conn.commit()
                        st.success("Relationship deleted successfully!")
                        st.experimental_rerun()
                    except Exception as e:
                        st.error(f"Failed to delete relationship: {e}")
            else:
                st.info("No relationships found.")
        else:
            st.info("Need at least 2 users to manage relationships.")

    close_card()

# ------------------------------
# Post Management (Add/Edit/Delete/View) with manual time entry option
# ------------------------------
elif choice == "Post Management":
    open_card("Post Management")
    tabs = st.tabs(["➕ Add Post", "🖊️ Edit Post", "❌ Delete Post", "📝 View Posts"])

    with tabs[0]:
        st.subheader("Create New Post")
        users_df = pd.read_sql_query("SELECT user_id, username FROM Users", conn)
        if users_df.empty:
            st.info("No users found — add users first.")
        else:
            uid = st.selectbox("Select Author", users_df["user_id"], 
                              format_func=lambda x: f"{users_df.loc[users_df['user_id']==x,'username'].values[0]} (ID: {x})",
                              key="post_author_select")
            content = st.text_area("Content", placeholder="Write your post content here...", height=150)
            likes = st.number_input("Likes", min_value=0, value=0, key="post_likes")
            
            # manual date + time entry
            col1, col2 = st.columns(2)
            with col1:
                date_input = st.date_input("Date", datetime.now().date(), key="post_date")
            with col2:
                time_input = st.text_input("Time (HH:MM:SS)", value=datetime.now().strftime("%H:%M:%S"), key="post_time")
            
            try:
                datetime.strptime(time_input, "%H:%M:%S")
                created_at = f"{date_input} {time_input}"
                time_valid = True
            except ValueError:
                created_at = None
                time_valid = False
                st.warning("Invalid time format. Use HH:MM:SS")

            if st.button("Add Post", key="add_post_btn"):
                if not content:
                    st.warning("Please provide post content.")
                elif not time_valid:
                    st.warning("Please provide a valid time format.")
                else:
                    try:
                        conn.execute("INSERT INTO Posts (user_id, content, likes, created_at) VALUES (?, ?, ?, ?)",
                                     (uid, content, likes, created_at))
                        conn.commit()
                        st.success("Post added successfully!")
                        st.experimental_rerun()
                    except Exception as e:
                        st.error(f"Failed to add post: {e}")

    with tabs[1]:
        st.subheader("Edit Existing Post")
        posts_df = pd.read_sql_query("SELECT post_id, content, user_id FROM Posts", conn)
        if posts_df.empty:
            st.info("No posts to edit.")
        else:
            pid = st.selectbox("Select post to edit", posts_df["post_id"], 
                              format_func=lambda x: f"Post {x}: {posts_df.loc[posts_df['post_id']==x,'content'].values[0][:50]}...",
                              key="edit_post_select")
            row = pd.read_sql_query("SELECT * FROM Posts WHERE post_id=?", conn, params=(pid,)).iloc[0]
            
            # Show current author
            author_df = pd.read_sql_query("SELECT username FROM Users WHERE user_id=?", conn, params=(row['user_id'],))
            current_author = author_df.iloc[0]['username'] if not author_df.empty else "Unknown"
            st.info(f"Current author: {current_author} (ID: {row['user_id']})")
            
            new_content = st.text_area("Content", value=row["content"], height=150, key="edit_post_content")
            new_likes = st.number_input("Likes", min_value=0, value=int(row.get("likes", 0)), key="edit_post_likes")
            
            if st.button("Update Post", key="update_post_btn"):
                try:
                    conn.execute("UPDATE Posts SET content=?, likes=? WHERE post_id=?", (new_content, new_likes, pid))
                    conn.commit()
                    st.success("Post updated successfully!")
                    st.experimental_rerun()
                except Exception as e:
                    st.error(f"Update failed: {e}")

    with tabs[2]:
        st.subheader("Delete Post")
        posts_df = pd.read_sql_query("SELECT post_id, content, user_id FROM Posts", conn)
        if posts_df.empty:
            st.info("No posts to delete.")
        else:
            pid_del = st.selectbox("Select post to delete", posts_df["post_id"], 
                                  format_func=lambda x: f"Post {x}: {posts_df.loc[posts_df['post_id']==x,'content'].values[0][:50]}...",
                                  key="delete_post_select")
            
            # Show post details before deletion
            if pid_del:
                post_details = posts_df[posts_df["post_id"] == pid_del].iloc[0]
                st.warning(f"You are about to delete Post {pid_del}")
                st.info(f"Content preview: {post_details['content'][:100]}...")
                
                # Check for comments
                comment_count = pd.read_sql_query("SELECT COUNT(*) as count FROM Comments WHERE post_id=?", conn, params=(pid_del,)).iloc[0]['count']
                if comment_count > 0:
                    st.warning(f"This post has {comment_count} comment(s) that will also be deleted!")
                
                if st.button("Confirm Delete", key="confirm_post_delete_btn"):
                    try:
                        # Delete comments first
                        conn.execute("DELETE FROM Comments WHERE post_id=?", (pid_del,))
                        # Delete the post
                        conn.execute("DELETE FROM Posts WHERE post_id=?", (pid_del,))
                        conn.commit()
                        st.success("Post and associated comments deleted successfully!")
                        st.experimental_rerun()
                    except Exception as e:
                        st.error(f"Delete failed: {e}")

    with tabs[3]:
        st.subheader("All Posts")
        try:
            posts_df = pd.read_sql_query("""
                SELECT p.post_id, p.user_id, u.username, p.content, p.likes, p.created_at,
                       COUNT(c.comment_id) as comment_count
                FROM Posts p
                JOIN Users u ON p.user_id = u.user_id
                LEFT JOIN Comments c ON p.post_id = c.post_id
                GROUP BY p.post_id
                ORDER BY p.created_at DESC
            """, conn)
            
            if not posts_df.empty:
                st.dataframe(posts_df, use_container_width=True)
                
                # Statistics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Posts", len(posts_df))
                with col2:
                    st.metric("Total Likes", posts_df['likes'].sum())
                with col3:
                    st.metric("Most Liked Post", f"{posts_df['likes'].max()} likes")
            else:
                st.info("No posts found.")
        except Exception as e:
            st.error(f"Error loading posts: {e}")

    close_card()

# close DB connection
conn.close()
