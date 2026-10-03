CREATE TABLE IF NOT EXISTS cold_chain.agent_audit_log (
    audit_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    thread_id VARCHAR(128) NOT NULL,
    user_question TEXT NOT NULL,
    tools_used VARCHAR(255) NOT NULL DEFAULT '',
    status VARCHAR(32) NOT NULL,
    error_message TEXT NULL,
    PRIMARY KEY (audit_id),
    INDEX idx_agent_audit_created_at (created_at),
    INDEX idx_agent_audit_thread_id (thread_id)
) ENGINE=InnoDB;

GRANT INSERT ON cold_chain.agent_audit_log
TO 'chain_agent_role';
