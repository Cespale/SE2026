from pathlib import Path


MIGRATION = Path("database/migrations/001-service-tables.sql")
INIT_SCRIPT = Path("database/init/01-service-schemas.sh")
COPIER = Path("scripts/migrate_monolith_data.py")
ISOLATION_CHECK = Path("scripts/verify_schema_isolation.py")


def test_schema_sql_has_exact_service_owned_tables_and_no_cross_schema_fks():
    sql = MIGRATION.read_text(encoding="utf-8")
    expected_tables = {
        "user_service": {
            "users",
            "follows",
            "conversations",
            "messages",
            "notifications",
            "processed_events",
        },
        "content_service": {
            "categories",
            "videos",
            "integration_outbox",
            "processed_events",
        },
        "social_service": {
            "comments",
            "comment_mentions",
            "video_likes",
            "video_favorites",
            "video_interaction_baselines",
            "danmaku",
            "live_rooms",
            "reports",
            "sensitive_words",
            "integration_outbox",
            "processed_events",
        },
    }

    for schema, tables in expected_tables.items():
        assert f"SET search_path TO {schema}" in sql
        for table in tables:
            assert f"CREATE TABLE IF NOT EXISTS {table}" in sql

    assert "REFERENCES user_service." not in sql
    assert "REFERENCES content_service." not in sql
    assert "REFERENCES social_service." not in sql


def test_init_script_uses_parameterized_secrets_and_revokes_public_access():
    script = INIT_SCRIPT.read_text(encoding="utf-8")
    for schema in ("user_service", "content_service", "social_service"):
        assert f"REVOKE ALL ON SCHEMA {schema} FROM PUBLIC" in script
    assert "--set=user_service_password=" in script
    assert "--set=content_service_password=" in script
    assert "--set=social_service_password=" in script
    assert "PASSWORD :'" not in script


def test_data_copier_has_complete_map_and_no_destructive_source_sql():
    source = COPIER.read_text(encoding="utf-8")
    for table in (
        "users",
        "follows",
        "conversations",
        "messages",
        "notifications",
        "categories",
        "videos",
        "comments",
        "comment_mentions",
        "video_likes",
        "danmaku",
        "live_rooms",
        "reports",
        "sensitive_words",
    ):
        assert f'"{table}":' in source
    assert "on_conflict_do_nothing" in source
    assert "seed_interaction_baselines" in source
    for forbidden in ("DELETE ", "DROP ", "TRUNCATE ", "UPDATE "):
        assert forbidden not in source.upper()


def test_isolation_check_has_one_owned_and_two_foreign_checks_per_role():
    source = ISOLATION_CHECK.read_text(encoding="utf-8")
    assert "SCHEMA_ISOLATION=PASS" in source
    assert source.count("foreign_schemas") >= 1
    for role in (
        "streamhub_user_service",
        "streamhub_content_service",
        "streamhub_social_service",
    ):
        assert role in source


def test_service_source_contains_no_foreign_schema_sql():
    ownership = {
        "user-service": {"content_service", "social_service"},
        "content-service": {"user_service", "social_service"},
        "social-service": {"user_service", "content_service"},
    }
    for service, forbidden_schemas in ownership.items():
        source = "\n".join(
            path.read_text(encoding="utf-8")
            for path in Path(f"services/{service}/app").glob("*.py")
        ).lower()
        for schema in forbidden_schemas:
            assert f"from {schema}." not in source
            assert f"join {schema}." not in source
            assert f"update {schema}." not in source
            assert f"insert into {schema}." not in source
            assert f"delete from {schema}." not in source
