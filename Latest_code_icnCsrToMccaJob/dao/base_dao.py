"""
Base JDBC-style DAO helper for AlloyDB (PostgreSQL) and Oracle compatibility.
"""

import logging
import re
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from reader_queries import adapt_sql

logger = logging.getLogger(__name__)


class BaseJdbcDao:
    """
    Provides Spring JdbcDaoSupport-equivalent methods (query, query_for_list,
    query_for_long, query_for_object, update) while converting `?` placeholders
    to `%s` for PostgreSQL/AlloyDB (psycopg2) and adapting Oracle SQL functions.
    """

    def __init__(self, connection: Any, dialect: str = "postgresql"):
        self.connection = connection
        self.dialect = dialect.lower()

    def _prepare_sql(self, sql: str) -> str:
        adapted = adapt_sql(sql, self.dialect)
        if self.dialect == "postgresql":
            # Replace JDBC '?' bind placeholders with psycopg2 '%s' outside single-quoted literals
            parts = re.split(r"('[^']*')", adapted)
            for idx in range(0, len(parts), 2):
                parts[idx] = parts[idx].replace("?", "%s")
            adapted = "".join(parts)
        return adapted

    def query_for_list(self, sql: str, params: Optional[Sequence[Any]] = None) -> List[Dict[str, Any]]:
        prepared_sql = self._prepare_sql(sql)
        with self.connection.cursor() as cur:
            cur.execute(prepared_sql, params or ())
            if not cur.description:
                return []
            columns = [col[0].upper() for col in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]

    def query(
        self,
        sql: str,
        row_mapper: Callable[[Dict[str, Any]], Any],
        params: Optional[Sequence[Any]] = None,
    ) -> List[Any]:
        rows = self.query_for_list(sql, params)
        return [row_mapper(row) for row in rows]

    def query_for_long(self, sql: str, params: Optional[Sequence[Any]] = None) -> int:
        prepared_sql = self._prepare_sql(sql)
        with self.connection.cursor() as cur:
            cur.execute(prepared_sql, params or ())
            row = cur.fetchone()
            if row and row[0] is not None:
                return int(row[0])
            return 0

    def query_for_object(self, sql: str, params: Optional[Sequence[Any]] = None) -> Any:
        prepared_sql = self._prepare_sql(sql)
        with self.connection.cursor() as cur:
            cur.execute(prepared_sql, params or ())
            row = cur.fetchone()
            return row[0] if row else None

    def update(self, sql: str, params: Optional[Sequence[Any]] = None) -> int:
        prepared_sql = self._prepare_sql(sql)
        with self.connection.cursor() as cur:
            cur.execute(prepared_sql, params or ())
            rowcount = cur.rowcount
        self.connection.commit()
        return rowcount
