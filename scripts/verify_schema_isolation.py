import os
import sys
from urllib.parse import quote_plus

import psycopg2
from dotenv import load_dotenv
from psycopg2.errors import InsufficientPrivilege


ROLE_CHECKS = {
    "streamhub_user_service": (
        "USER_SERVICE_DB_PASSWORD",
        "user_service.users",
        ("content_service.categories", "social_service.comments"),
    ),
    "streamhub_content_service": (
        "CONTENT_SERVICE_DB_PASSWORD",
        "content_service.categories",
        ("user_service.users", "social_service.comments"),
    ),
    "streamhub_social_service": (
        "SOCIAL_SERVICE_DB_PASSWORD",
        "social_service.comments",
        ("user_service.users", "content_service.categories"),
    ),
}


def connection_url(role: str, password_name: str) -> str:
    password = os.environ[password_name]
    host = os.getenv("MICROSERVICES_DB_HOST", "127.0.0.1")
    port = os.getenv("MICROSERVICES_DB_PORT", "5434")
    database = os.getenv("POSTGRES_DB", "streamhub")
    return (
        f"postgresql://{quote_plus(role)}:{quote_plus(password)}"
        f"@{host}:{port}/{quote_plus(database)}"
    )


def verify_role(role: str, password_name: str, owned_table: str, foreign_schemas: tuple[str, str]) -> None:
    connection = psycopg2.connect(connection_url(role, password_name))
    connection.autocommit = True
    try:
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT 1 FROM {owned_table} LIMIT 1")
            for foreign_table in foreign_schemas:
                try:
                    cursor.execute(f"SELECT 1 FROM {foreign_table} LIMIT 1")
                except InsufficientPrivilege:
                    continue
                raise AssertionError(f"foreign Schema is readable by {role}")
    finally:
        connection.close()


def main() -> int:
    load_dotenv(".env.microservices")
    try:
        for role, check in ROLE_CHECKS.items():
            verify_role(role, *check)
    except Exception as exc:
        print(f"SCHEMA_ISOLATION=FAIL type={type(exc).__name__}", file=sys.stderr)
        return 1

    print("SCHEMA_ISOLATION=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
