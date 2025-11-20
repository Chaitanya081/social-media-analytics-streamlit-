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
# Streamlit Page Config
# -------------------------------------------------------
st.set_page_config(page_title="Social Media Analytics Platform", layout="wide")

# -------------------------------------------------------
# Load Background Image (LOGIN PAGE ONLY)
# -------------------------------------------------------
LOGIN_BG = "data/SocialMedia1.png"

LOGIN_CSS = f"""
<style>
/* FULL SCREEN BACKGROUND */
.stApp {{
    background: url("{LOGIN_BG}") no-repeat center center fixed;
    background-size: cover;
}}

/* GLASS CENTER CARD */
.login-card {{
    margin: 80px auto;
    width: 55%;
    background: rgba(0, 0, 0, 0.55);
    padding: 35px;
    border-radius: 18px;
    box-shadow: 0px 0px 25px rgba(0,0,0,0.6);
    backdrop-filter: blur(8px);
    color: white;
    text-align: center;
}}

.login-title {{
    font-size: 36px;
    font-weight: 900;
    margin-bottom: 8px;
}}

.sub-text {{
    font-size: 16px;
    opacity: 0.9;
    margin-bottom: 20px;
}}

/* INPUT BOX GLASS EFFECT */
.stTextInput > div > div > input {{
    background: rgba(255,255,255,0.2);
    color: white;
    border-radius: 10px;
}}

.stTextInput label {{
    color: #fff !important;
}}

.stPasswordInput > div > div > input {{
    background: rgba(255,255,255,0.2);
    color: white;
    border-radius: 10px;
}}

</style>
"""

# -------------------------------------------------------
# Database Setup
# -------------------------------------------------------
TEMP_DIR = tempfile.gettempdir()
DB_PATH = os.path.join(TEMP_DIR, "social_media.db")

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def ensure_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Load schema
    if os.path.exists("db/schema.sql"):
        with open("db/schema.sql", "r") as f:
            cursor.executescript(f.read())

    # Ensure password column
    cursor.execute("PRAGMA table_info(Users);")
    cols = [c[1] for c in cursor.fetchall()]
    if "password" not in cols:
        cursor.execute("ALTER TABLE Users ADD COLUMN password TEXT;")
        conn.commit()

    # Load sample data
    cursor.execute("SELECT COUNT(*) FROM Users;")
    if cursor.fetchone()[0] == 0 and os.path.exists("db/sample_data.sql"):
        with open("db/sample_data.sql", "r") as f:
            cursor.executescript(f.read())

    conn.commit()
    conn.close()

ensure_database()

# -------------------------------------------------------
# Authentication Functions
# -------------------------------------------------------
def verify_user(email, password):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    hashed = hash_password(password)
    cursor.execute("SELECT * FROM Users WHERE email=? AND password=?", (email, hashed))
    user = cursor.fetchone()
    conn.close()
    return user

def register_user(username, email, password):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    hashed = hash_password(password)
    try:
        cursor.execute("INSERT INTO Users (username, email, password) VALUES (?, ?, ?);",
                       (username, email, hashed))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        conn.close()
        return str(e)

# -------------------------------------------------------
# LOGIN PAGE (Custom UI with Background Image)
# -------------------------------------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:

    st.markdown(LOGIN_CSS, unsafe_allow_html=True)

    # Glass Card Layout
    st.markdown('<div class="login-card">', unsafe_allow_html=True)

    st.markdown('<div class="login-title">SOCIAL MEDIA ANALYTICS PLATFORM</div>',
                unsafe_allow_html=True)
    st.markdown('<div class="sub-text">Welcome! Please log in to continue.</div>',
                unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["🔑 Login", "🆕 Register"])

    # LOGIN TAB
    with tab1:
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        if st.button("Sign In"):
            user = verify_user(email, password)
            if user:
                st.session_state.logged_in = True
                st.session_state.username = user[1]
                st.success("Login successful!")
                st.rerun()
            else:
                st.error("Invalid credentials")

    # REGISTER TAB
    with tab2:
        username = st.text_input("New Username")
        r_email = st.text_input("New Email")
        r_pw = st.text_input("New Password", type="password")

        if st.button("Register"):
            if username and r_email and r_pw:
                result = register_user(username, r_email, r_pw)
                if result is True:
                    st.success("Registration completed! Please log in.")
                else:
                    st.error(result)
            else:
                st.warning("Fill all fields.")

    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# -------------------------------------------------------
# AFTER LOGIN — Restore Normal UI
# -------------------------------------------------------

st.sidebar.success(f"👋 Logged in as {st.session_state.username}")

if st.sidebar.button("🚪 Logout"):
    st.session_state.logged_in = False
    st.rerun()

conn = sqlite3.connect(DB_PATH)

choice = st.sidebar.selectbox(
    "Select Module",
    ["Database Overview", "Analytics", "Performance", "User Management", "Post Management"]
)

# -------------------------------------------------------
# MODULE: Database Overview
# -------------------------------------------------------
if choice == "Database Overview":
    st.header("📘 Database Overview")
    users = pd.read_sql_query("SELECT user_id, username, email FROM Users", conn)
    posts = pd.read_sql_query("SELECT * FROM Posts", conn)
    st.subheader("Users")
    st.dataframe(users)
    st.subheader("Posts")
    st.dataframe(posts)

# -------------------------------------------------------
# MODULE: Analytics
# -------------------------------------------------------
elif choice == "Analytics":
    st.header("📊 Analytics")
    option = st.selectbox("Choose Analysis", [
        "Most Active Users", "Top Influencers", "Trending Posts"
    ])
    start = time.time()

    if option == "Most Active Users":
        q = """
        SELECT u.username,
        COUNT(p.post_id) + COUNT(c.comment_id) AS total_activity
        FROM Users u
        LEFT JOIN Posts p ON u.user_id=p.user_id
        LEFT JOIN Comments c ON u.user_id=c.user_id
        GROUP BY u.username
        ORDER BY total_activity DESC LIMIT 10;
        """
        df = pd.read_sql_query(q, conn)
        st.bar_chart(df.set_index("username"))

    elif option == "Top Influencers":
        q = """
        SELECT u.username, COUNT(r.following_id) AS followers
        FROM Users u
        JOIN Relationships r ON u.user_id=r.following_id
        GROUP BY u.username ORDER BY followers DESC LIMIT 10;
        """
        df = pd.read_sql_query(q, conn)
        st.bar_chart(df.set_index("username"))

    elif option == "Trending Posts":
        q = """
        SELECT p.post_id, p.content,
        (p.likes + COUNT(c.comment_id)) AS engagement_score
        FROM Posts p
        LEFT JOIN Comments c ON p.post_id=c.post_id
        GROUP BY p.post_id ORDER BY engagement_score DESC LIMIT 5;
        """
        df = pd.read_sql_query(q, conn)
        st.dataframe(df)

    st.info(f"Query time: {round(time.time()-start, 4)} sec")

# -------------------------------------------------------
# MODULE: Performance
# -------------------------------------------------------
elif choice == "Performance":
    st.header("⚡ Performance Optimization")
    if st.button("Create Indexes"):
        create_indexes(conn)
        st.success("Indexes created!")
    if os.path.exists("data/performance_chart.png"):
        st.image("data/performance_chart.png")

# -------------------------------------------------------
# MODULE: User Management
# -------------------------------------------------------
elif choice == "User Management":
    st.header("👤 User Management")
    df = pd.read_sql_query("SELECT user_id, username, email FROM Users", conn)
    st.dataframe(df)

# -------------------------------------------------------
# MODULE: Post Management
# -------------------------------------------------------
elif choice == "Post Management":
    st.header("📝 Post Management")

    tab1, tab2 = st.tabs(["➕ Add Post", "❌ Delete Post"])

    with tab1:
        users_df = pd.read_sql_query("SELECT user_id, username FROM Users", conn)
        if not users_df.empty:
            uid = st.selectbox("Select User", users_df["user_id"],
                               format_func=lambda x: users_df.loc[users_df["user_id"]==x,"username"].values[0])
            content = st.text_area("Content")
            likes = st.number_input("Likes", min_value=0)
            date = st.date_input("Date", datetime.now().date())
            time_str = st.text_input("Time (HH:MM:SS)", value=datetime.now().strftime("%H:%M:%S"))

            try:
                datetime.strptime(time_str, "%H:%M:%S")
                created_at = f"{date} {time_str}"
            except:
                st.warning("Invalid time format")
                created_at = None

            if st.button("Add Post"):
                if content and created_at:
                    conn.execute("INSERT INTO Posts (user_id,content,likes,created_at) VALUES (?,?,?,?)",
                                 (uid, content, likes, created_at))
                    conn.commit()
                    st.success("Post Added!")

    with tab2:
        posts = pd.read_sql_query("SELECT post_id, content FROM Posts", conn)
        if not posts.empty:
            pid = st.selectbox("Select Post to Delete", posts["post_id"],
                format_func=lambda x: posts.loc[posts["post_id"]==x, "content"].values[0])
            if st.button("Delete Post"):
                conn.execute("DELETE FROM Posts WHERE post_id=?", (pid,))
                conn.commit()
                st.success("Post Deleted!")

conn.close()
