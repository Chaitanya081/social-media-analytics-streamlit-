INSERT INTO Users (username, email, password) VALUES
('Alice', 'alice@example.com', 'e99a18c428cb38d5f260853678922e03'),  -- password
('Bob', 'bob@example.com', 'e99a18c428cb38d5f260853678922e03'),
('Charlie', 'charlie@example.com', 'e99a18c428cb38d5f260853678922e03');

INSERT INTO Posts (user_id, content, likes, created_at) VALUES
(1, 'Hello World!', 5, '2024-01-15 10:22:00'),
(2, 'My first post!', 12, '2024-02-20 15:45:00'),
(3, 'Nice weather today!', 7, '2024-03-01 09:10:00');

INSERT INTO Comments (post_id, user_id, content, created_at) VALUES
(1, 2, 'Nice post!', '2024-01-15 11:00:00'),
(1, 3, 'Agree!', '2024-01-15 11:20:00'),
(2, 1, 'Good start!', '2024-02-20 16:00:00');

INSERT INTO Relationships (follower_id, following_id) VALUES
(1, 2),
(2, 3),
(3, 1);
