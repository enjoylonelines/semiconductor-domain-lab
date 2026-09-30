from unittest import TestCase
from unittest.mock import patch

from eda_lab.postgres_store import PostgresStore


class PostgresStoreInitializationTests(TestCase):
    def test_runtime_connection_can_skip_schema_migration(self):
        with patch("eda_lab.postgres_store.psycopg.connect", return_value=object()), \
             patch.object(PostgresStore, "_migrate") as migrate:
            PostgresStore("postgresql://example", migrate=False)

        migrate.assert_not_called()

    def test_schema_migration_remains_default_for_existing_callers(self):
        with patch("eda_lab.postgres_store.psycopg.connect", return_value=object()), \
             patch.object(PostgresStore, "_migrate") as migrate:
            PostgresStore("postgresql://example")

        migrate.assert_called_once_with()
