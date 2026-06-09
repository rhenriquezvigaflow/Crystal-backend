CREATE TABLE IF NOT EXISTS auth_2fa_challenge (
    id UUID PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    code_hash TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    consumed_at TIMESTAMPTZ NULL,
    attempts INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_auth_2fa_challenge_user_id
    ON auth_2fa_challenge (user_id);

CREATE INDEX IF NOT EXISTS ix_auth_2fa_challenge_user_active
    ON auth_2fa_challenge (user_id, consumed_at, expires_at);
