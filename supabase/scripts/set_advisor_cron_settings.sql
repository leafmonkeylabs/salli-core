-- Store the two values the daily-advisor pg_cron job reads at run time.
--
-- Run with psql -f and both variables supplied:
--   psql -v url='https://…/advisor/cron/run-due' -v secret='…' \
--        -f supabase/scripts/set_advisor_cron_settings.sql
--
-- A file rather than `psql -c`: variable interpolation (`:'url'`) only happens
-- for commands read from a file or stdin, and passing the secret this way keeps
-- it out of the process command line.
--
-- Supabase Vault rather than `ALTER DATABASE … SET`, which is denied — the
-- `postgres` role there is not a superuser and cannot set custom parameters:
--
--   ERROR: permission denied to set parameter "app.salli_advisor_url"
--
-- Vault keeps the secret encrypted at rest, which a database setting or a plain
-- config table would not.
--
-- Delete-then-create rather than an upsert: `create_secret` returns a uuid while
-- `update_secret` returns void, so branching between them needs a DO block — and
-- psql does not interpolate `:'url'` inside a dollar-quoted body, which is
-- exactly where the value would have to go. Deleting first sidesteps that and is
-- just as idempotent.

create extension if not exists supabase_vault with schema vault;

delete from vault.secrets where name in ('salli_advisor_url', 'salli_cron_secret');

select vault.create_secret(
  :'url',
  'salli_advisor_url',
  'Daily advisor cron endpoint, read by the salli-daily-advisor pg_cron job'
);

select vault.create_secret(
  :'secret',
  'salli_cron_secret',
  'Shared secret sent as X-Cron-Secret; must match the API''s CRON_SECRET'
);
