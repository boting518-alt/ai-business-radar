BEGIN;

ALTER TABLE review_tasks
    ADD COLUMN resolved_by UUID NULL,
    ADD CONSTRAINT fk_review_tasks_resolved_by
        FOREIGN KEY (resolved_by) REFERENCES user_profiles(id) ON DELETE SET NULL;

CREATE INDEX idx_review_tasks_resolved_by ON review_tasks (resolved_by);

COMMIT;
