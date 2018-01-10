DO $$
BEGIN
IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='albumlistbot') THEN
   REVOKE ALL PRIVILEGES ON DATABASE postgres FROM albumlistbot;
END IF;
END$$;

DROP SCHEMA IF EXISTS albumlistbot CASCADE;
DROP ROLE IF EXISTS albumlistbot;

CREATE ROLE albumlistbot PASSWORD 'albumlistbot'
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION INHERIT LOGIN;

CREATE SCHEMA albumlistbot AUTHORIZATION albumlistbot;

REVOKE ALL ON ALL TABLES IN SCHEMA albumlistbot FROM PUBLIC;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA albumlistbot FROM PUBLIC;
REVOKE CONNECT ON DATABASE postgres FROM PUBLIC;

GRANT CONNECT ON DATABASE postgres TO albumlistbot;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA albumlistbot TO albumlistbot;
GRANT ALL ON ALL SEQUENCES IN SCHEMA albumlistbot TO albumlistbot;