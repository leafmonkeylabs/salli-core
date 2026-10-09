-- Daily Wealth Advisor schedule (Supabase pg_cron → API).
--
-- The URL and cron secret are NOT hard-coded here (no secrets in git). They live
-- in Supabase Vault and the job reads them at run time. Install them first with:
--
--   psql -v url='https://…/advisor/cron/run-due' -v secret='<CRON_SECRET>' \
--        -f supabase/scripts/set_advisor_cron_settings.sql
--
-- or let the "Daily advisor cron (setup)" workflow do both in order.
--
-- Vault rather than database settings: this originally read `current_setting`
-- values set with `ALTER DATABASE … SET`, which Supabase denies — its `postgres`
-- role is not a superuser ("permission denied to set parameter"). Vault is the
-- supported way to hold a secret a scheduled job needs, and encrypts it at rest.
--
-- If the secrets are missing the job no-ops rather than firing an unauthenticated
-- request, so installing the schedule before the secrets is harmless.

create extension if not exists pg_cron;
create extension if not exists pg_net;
create extension if not exists supabase_vault with schema vault;

-- Re-running this migration replaces the schedule cleanly.
select cron.unschedule('salli-daily-advisor')
where exists (select 1 from cron.job where jobname = 'salli-daily-advisor');

-- 06:00 UTC daily. The job fires the secured endpoint, which fans out to the
-- users who opted into a daily briefing and skips anyone already run today.
select cron.schedule(
  'salli-daily-advisor',
  '0 6 * * *',
  $job$
  select
    case
      when (select decrypted_secret from vault.decrypted_secrets
            where name = 'salli_advisor_url') is null then null
      else net.http_post(
        url     := (select decrypted_secret from vault.decrypted_secrets
                    where name = 'salli_advisor_url'),
        headers := jsonb_build_object(
          'Content-Type', 'application/json',
          'X-Cron-Secret', coalesce(
            (select decrypted_secret from vault.decrypted_secrets
             where name = 'salli_cron_secret'), '')
        ),
        body    := '{}'::jsonb,
        -- Explicit, because pg_net's default is a few seconds and the API is on
        -- a Render plan that sleeps: a cold start takes far longer than that, so
        -- the request would time out before the service ever woke. The endpoint
        -- itself returns 202 immediately and runs the advisor in a background
        -- task, so this budget only has to cover waking up and one query.
        timeout_milliseconds := 90000
      )
    end;
  $job$
);
