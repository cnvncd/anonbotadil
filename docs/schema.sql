-- SQL schema (auto-generated reference; bot uses SQLAlchemy to create tables)
-- Run: python -m bot.main  (tables created automatically on first start)

-- Enum types
CREATE TYPE content_type_enum AS ENUM (
    'text', 'photo', 'video', 'voice', 'document', 'link', 'media_group'
);

CREATE TYPE post_status_enum AS ENUM (
    'pending', 'approved', 'rejected', 'scheduled', 'archived', 'published'
);

-- Users table
CREATE TABLE users (
    id           SERIAL PRIMARY KEY,
    telegram_id  BIGINT NOT NULL UNIQUE,
    username     VARCHAR(64),
    registered_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_telegram_id ON users(telegram_id);

-- Posts table
CREATE TABLE posts (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    content_type    content_type_enum NOT NULL,
    text            TEXT,
    media_file_id   VARCHAR(1024),
    status          post_status_enum NOT NULL DEFAULT 'pending',
    admin_message_id BIGINT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    scheduled_time  TIMESTAMPTZ,
    published_at    TIMESTAMPTZ
);

CREATE INDEX idx_posts_user_id ON posts(user_id);
CREATE INDEX idx_posts_status  ON posts(status);
CREATE INDEX idx_posts_scheduled ON posts(scheduled_time) WHERE status = 'scheduled';
