CREATE TABLE IF NOT EXISTS Users (
  user_id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT UNIQUE,
  email TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS Posts (
  post_id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INT REFERENCES Users(user_id),
  content TEXT,
  likes INT DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS Comments (
  comment_id INTEGER PRIMARY KEY AUTOINCREMENT,
  post_id INT REFERENCES Posts(post_id),
  user_id INT REFERENCES Users(user_id),
  content TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS Relationships (
  follower_id INT REFERENCES Users(user_id),
  following_id INT REFERENCES Users(user_id),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (follower_id, following_id)
);
