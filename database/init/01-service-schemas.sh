#!/usr/bin/env bash
set -Eeuo pipefail

: "${POSTGRES_USER:?POSTGRES_USER is required}"
: "${POSTGRES_DB:?POSTGRES_DB is required}"
: "${USER_SERVICE_DB_PASSWORD:?USER_SERVICE_DB_PASSWORD is required}"
: "${CONTENT_SERVICE_DB_PASSWORD:?CONTENT_SERVICE_DB_PASSWORD is required}"
: "${SOCIAL_SERVICE_DB_PASSWORD:?SOCIAL_SERVICE_DB_PASSWORD is required}"

psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set=user_service_password="$USER_SERVICE_DB_PASSWORD" \
  --set=content_service_password="$CONTENT_SERVICE_DB_PASSWORD" \
  --set=social_service_password="$SOCIAL_SERVICE_DB_PASSWORD" <<'SQL'
\set ON_ERROR_STOP on

SELECT format(
  'CREATE ROLE %I LOGIN PASSWORD %L',
  'streamhub_user_service',
  :'user_service_password'
) WHERE NOT EXISTS (
  SELECT 1 FROM pg_roles WHERE rolname = 'streamhub_user_service'
) \gexec
SELECT format(
  'CREATE ROLE %I LOGIN PASSWORD %L',
  'streamhub_content_service',
  :'content_service_password'
) WHERE NOT EXISTS (
  SELECT 1 FROM pg_roles WHERE rolname = 'streamhub_content_service'
) \gexec
SELECT format(
  'CREATE ROLE %I LOGIN PASSWORD %L',
  'streamhub_social_service',
  :'social_service_password'
) WHERE NOT EXISTS (
  SELECT 1 FROM pg_roles WHERE rolname = 'streamhub_social_service'
) \gexec

SELECT format(
  'ALTER ROLE %I LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE',
  'streamhub_user_service',
  :'user_service_password'
) \gexec
SELECT format(
  'ALTER ROLE %I LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE',
  'streamhub_content_service',
  :'content_service_password'
) \gexec
SELECT format(
  'ALTER ROLE %I LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE',
  'streamhub_social_service',
  :'social_service_password'
) \gexec

CREATE SCHEMA IF NOT EXISTS user_service AUTHORIZATION streamhub_user_service;
CREATE SCHEMA IF NOT EXISTS content_service AUTHORIZATION streamhub_content_service;
CREATE SCHEMA IF NOT EXISTS social_service AUTHORIZATION streamhub_social_service;

ALTER SCHEMA user_service OWNER TO streamhub_user_service;
ALTER SCHEMA content_service OWNER TO streamhub_content_service;
ALTER SCHEMA social_service OWNER TO streamhub_social_service;

REVOKE ALL ON SCHEMA user_service FROM PUBLIC;
REVOKE ALL ON SCHEMA content_service FROM PUBLIC;
REVOKE ALL ON SCHEMA social_service FROM PUBLIC;

GRANT USAGE, CREATE ON SCHEMA user_service TO streamhub_user_service;
GRANT USAGE, CREATE ON SCHEMA content_service TO streamhub_content_service;
GRANT USAGE, CREATE ON SCHEMA social_service TO streamhub_social_service;

ALTER DEFAULT PRIVILEGES FOR ROLE streamhub_user_service IN SCHEMA user_service
  REVOKE ALL ON TABLES FROM PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE streamhub_content_service IN SCHEMA content_service
  REVOKE ALL ON TABLES FROM PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE streamhub_social_service IN SCHEMA social_service
  REVOKE ALL ON TABLES FROM PUBLIC;
SQL
