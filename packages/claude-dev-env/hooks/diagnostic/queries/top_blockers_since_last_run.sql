-- Top 10 hooks by blocking count in the last 24 hours.
SELECT
    hook_name,
    hook_category,
    COUNT(*) AS block_count_since_last_run,
    MIN(COALESCE(command_excerpt, stdout_excerpt, stderr_excerpt, '')) AS top_blocked_command_preview
FROM hook_events
WHERE outcome = 'blocked'
    AND event_timestamp >= (NOW() - INTERVAL '1 day')
GROUP BY hook_name, hook_category
ORDER BY block_count_since_last_run DESC
LIMIT 10;
