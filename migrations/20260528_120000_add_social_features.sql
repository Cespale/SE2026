-- 社区互动功能:关注、私聊、通知、@提及
-- 注意:启动时 Base.metadata.create_all + apply_social_migration 会自动应用,
-- 本文件仅作记录与手动恢复用。

ALTER TABLE comments ADD COLUMN IF NOT EXISTS reply_to_user_id UUID REFERENCES users(id);

CREATE TABLE IF NOT EXISTS follows (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    follower_id UUID NOT NULL REFERENCES users(id),
    followee_id UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_follow_pair UNIQUE (follower_id, followee_id)
);
CREATE INDEX IF NOT EXISTS ix_follows_follower ON follows (follower_id);
CREATE INDEX IF NOT EXISTS ix_follows_followee ON follows (followee_id);

CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_a_id UUID NOT NULL REFERENCES users(id),
    user_b_id UUID NOT NULL REFERENCES users(id),
    last_message_id UUID,
    last_message_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_conversation_pair UNIQUE (user_a_id, user_b_id)
);

CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id),
    sender_id UUID NOT NULL REFERENCES users(id),
    receiver_id UUID NOT NULL REFERENCES users(id),
    content TEXT NOT NULL,
    message_type SMALLINT DEFAULT 0,
    is_recalled BOOLEAN DEFAULT FALSE,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    recalled_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_messages_conv_created ON messages (conversation_id, created_at);
CREATE INDEX IF NOT EXISTS ix_messages_receiver_unread ON messages (receiver_id, is_read);

CREATE TABLE IF NOT EXISTS notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recipient_id UUID NOT NULL REFERENCES users(id),
    sender_id UUID REFERENCES users(id),
    notif_type SMALLINT DEFAULT 0,
    target_type SMALLINT DEFAULT 0,
    target_id UUID,
    content TEXT DEFAULT '',
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_notif_recipient_unread
    ON notifications (recipient_id, is_read, created_at);

CREATE TABLE IF NOT EXISTS comment_mentions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    comment_id UUID NOT NULL REFERENCES comments(id),
    mentioned_user_id UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_comment_mention UNIQUE (comment_id, mentioned_user_id)
);
CREATE INDEX IF NOT EXISTS ix_mention_user ON comment_mentions (mentioned_user_id);
