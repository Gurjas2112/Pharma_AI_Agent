| Data | Store | Retention |
|---|---|---|
| audit_log | Supabase (append-only; RLS denies client access) | 1 year |
| CloudWatch /repurpora/audit | AWS (LocalStack in prototype) | 90 days (put-retention-policy) |
| llm_usage | Supabase | 180 days |
| Reports (PDF/XLSX) | Supabase Storage `reports` (private, 7-day signed URLs) + S3 mirror (SSE-AES256) | 3 years |
| Threads / checkpoints | Aegra Postgres | until the user deletes them |
