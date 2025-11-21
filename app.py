import streamlit as st
import sqlite3
import pandas as pd
import hashlib
from datetime import datetime

# ----------------------------------------------------------
# PAGE CONFIG
# ----------------------------------------------------------
st.set_page_config(page_title="Social Media Analytics Platform", layout="wide")

# ----------------------------------------------------------
# DATABASE + PASSWORD HASH
# ----------------------------------------------------------
DB = "social.db"

def hash_pw(password):
    return hashlib.sha256(password.encode()).hexdigest()

def init_db():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            email TEXT UNIQUE,
            password TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            post_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            content TEXT,
            created_at TEXT
        )
    """)

    conn.commit()
    conn.close()

init_db()

# ----------------------------------------------------------
# AUTH FUNCTIONS
# ----------------------------------------------------------
def register(username, email, password):
    try:
        conn = sqlite3.connect(DB)
        cur = conn.cursor()
        cur.execute("INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
                    (username, email, hash_pw(password)))
        conn.commit()
        conn.close()
        return True
    except:
        return False

def login(email, password):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email=? AND password=?",
                (email, hash_pw(password)))
    data = cur.fetchone()
    conn.close()
    return data

# ----------------------------------------------------------
# LOGIN PAGE UI (FULL PAGE IMAGE)
# ----------------------------------------------------------
def login_page():

    st.markdown("""
        <style>
            .main {
                background-image: url('https://i.ibb.co/XYfksQt/social-bg.jpg');
                background-size: cover;
            }
            .login-box {
                background: rgba(0,0,0,0.65);
                padding: 40px;
                border-radius: 15px;
                width: 450px;
                margin: auto;
                margin-top: 80px;
            }
            .title-text {
                color: white;
                text-align: center;
                font-size: 35px;
                font-weight: bold;
            }
            .subtitle {
                text-align: center;
                color: #ddd;
                margin-bottom: 20px;
            }
        </style>
    """, unsafe_allow_html=True)

    st.markdown("<div class='login-box'>", unsafe_allow_html=True)
    st.markdown("<div class='title-text'>SOCIAL MEDIA ANALYTICS PLATFORM</div>", unsafe_allow_html=True)
    st.markdown("<div class='subtitle'>Welcome! Please log in to continue.</div>", unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["🔑 Login", "🆕 Register"])

    with tab1:
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        if st.button("Sign In"):
            user = login(email, password)
            if user:
                st.session_state.logged = True
                st.session_state.user = user
                st.rerun()
            else:
                st.error("Invalid credentials")

    with tab2:
        uname = st.text_input("New Username")
        mail = st.text_input("New Email")
        pw = st.text_input("New Password", type="password")
        if st.button("Create Account"):
            if register(uname, mail, pw):
                st.success("Registration successful!")
            else:
                st.error("Email already exists!")

    st.markdown("</div>", unsafe_allow_html=True)

# ----------------------------------------------------------
# DASHBOARD PAGE
# ----------------------------------------------------------
def dashboard():
    st.title("📊 Dashboard")
    st.write("Welcome to Social Media Analytics Dashboard!")

# ----------------------------------------------------------
# USER MANAGEMENT PAGE
# ----------------------------------------------------------
def user_management():
    st.title("👤 Manage Users")

    conn = sqlite3.connect(DB)
    df = pd.read_sql_query("SELECT user_id, username, email FROM users", conn)
    st.dataframe(df)
    conn.close()

# ----------------------------------------------------------
# POST MANAGEMENT PAGE
# ----------------------------------------------------------
def post_management():
    st.title("📝 Post Management")

    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    users = pd.read_sql_query("SELECT user_id, username FROM users", conn)

    if not users.empty:
        uid = st.selectbox("Select User", users['user_id'],
                           format_func=lambda x: users[users.user_id == x].username.values[0])
        content = st.text_area("Post Content")

        if st.button("Add Post"):
            cur.execute("INSERT INTO posts (user_id, content, created_at) VALUES (?, ?, ?)",
                        (uid, content, str(datetime.now())))
            conn.commit()
            st.success("Post added successfully!")

    df = pd.read_sql_query("SELECT * FROM posts", conn)
    st.dataframe(df)
    conn.close()

# ----------------------------------------------------------
# ANALYTICS PAGE
# ----------------------------------------------------------
def analytics_page():
    st.title("📈 Analytics")

    conn = sqlite3.connect(DB)
    df = pd.read_sql_query("""
        SELECT u.username, COUNT(p.post_id) AS posts
        FROM users u
        LEFT JOIN posts p ON u.user_id = p.user_id
        GROUP BY u.user_id
    """, conn)

    st.bar_chart(df.set_index("username"))
    conn.close()

# ----------------------------------------------------------
# MAIN APP
# ----------------------------------------------------------
if "logged" not in st.session_state:
    st.session_state.logged = False

if not st.session_state.logged:
    login_page()
    st.stop()

# LEFT SIDEBAR
st.sidebar.success(f"Logged in as {st.session_state.user[1]}")

if st.sidebar.button("Logout"):
    st.session_state.logged = False
    st.rerun()

# MODULE SELECTOR
choice = st.sidebar.selectbox("Select Module", 
                              ["Dashboard", "User Management", "Post Management", "Analytics"])

# ROUTING
if choice == "Dashboard":
    dashboard()
elif choice == "User Management":
    user_management()
elif choice == "Post Management":
    post_management()
elif choice == "Analytics":
    analytics_page()
