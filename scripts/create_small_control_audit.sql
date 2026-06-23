CREATE TABLE IF NOT EXISTS small_control_audit (
    id UUID PRIMARY KEY,
    lagoon_id VARCHAR(150) NOT NULL,
    module_id VARCHAR(150) NOT NULL,
    control_type VARCHAR(50) NOT NULL,
    action VARCHAR(150) NOT NULL,
    command_id VARCHAR(150) NULL,
    tag_id VARCHAR(150) NULL,
    node_id VARCHAR(150) NULL,
    previous_value JSONB NULL,
    new_value JSONB NULL,
    change_summary VARCHAR(500) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'pending',
    error_detail VARCHAR(1000) NULL,
    user_id VARCHAR(150) NOT NULL,
    user_email VARCHAR(320) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ NULL
);

CREATE INDEX IF NOT EXISTS ix_small_control_audit_lagoon_id
    ON small_control_audit (lagoon_id);
CREATE INDEX IF NOT EXISTS ix_small_control_audit_module_id
    ON small_control_audit (module_id);
CREATE INDEX IF NOT EXISTS ix_small_control_audit_control_type
    ON small_control_audit (control_type);
CREATE INDEX IF NOT EXISTS ix_small_control_audit_status
    ON small_control_audit (status);
CREATE INDEX IF NOT EXISTS ix_small_control_audit_user_id
    ON small_control_audit (user_id);
CREATE INDEX IF NOT EXISTS ix_small_control_audit_user_email
    ON small_control_audit (user_email);
CREATE INDEX IF NOT EXISTS ix_small_control_audit_created_at
    ON small_control_audit (created_at);
