BEGIN;

ALTER TABLE review_tasks DROP CONSTRAINT ck_review_tasks_review_type;
ALTER TABLE review_tasks
    ADD CONSTRAINT ck_review_tasks_review_type CHECK (
        review_type IN (
            'signal_validation', 'opportunity_match', 'opportunity_merge',
            'opportunity_creation', 'opportunity_activation',
            'hype_review', 'quality_review'
        )
    );

COMMIT;
