import re


class QueryBuilder:
    """Safe, parameterised SQL query construction."""

    _IDENT_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

    @staticmethod
    def _validate_identifier(name: str):
        if not QueryBuilder._IDENT_RE.match(name):
            raise ValueError(f"Invalid identifier: {name}")

    @classmethod
    def select(cls, table: str, columns: list[str] | None = None, where: str | None = None,
               order_by: str | None = None, limit: int | None = None, offset: int | None = None) -> tuple[str, dict]:
        cls._validate_identifier(table)
        cols = ", ".join(columns) if columns else "*"
        sql = f"SELECT {cols} FROM {table}"  # noqa: S608
        params: dict = {}
        if where:
            sql += f" WHERE {where}"
        if order_by:
            cls._validate_identifier(order_by.lstrip("-"))
            direction = "DESC" if order_by.startswith("-") else "ASC"
            col = order_by.lstrip("-")
            sql += f" ORDER BY {col} {direction}"
        if limit is not None:
            sql += " LIMIT :limit"
            params["limit"] = limit
        if offset is not None:
            sql += " OFFSET :offset"
            params["offset"] = offset
        return sql, params

    @classmethod
    def aggregate(cls, table: str, group_col: str, agg_col: str, agg_func: str = "SUM",
                  where: str | None = None, having: str | None = None) -> tuple[str, dict]:
        cls._validate_identifier(table)
        cls._validate_identifier(group_col)
        cls._validate_identifier(agg_col)
        valid_funcs = {"SUM", "AVG", "COUNT", "MIN", "MAX"}
        af = agg_func.upper()
        if af not in valid_funcs:
            raise ValueError(f"Unsupported aggregate: {af}")
        sql = f"SELECT {group_col}, {af}({agg_col}) AS aggregated_value FROM {table}"  # noqa: S608
        params: dict = {}
        if where:
            sql += f" WHERE {where}"
        sql += f" GROUP BY {group_col}"
        if having:
            sql += f" HAVING {having}"
        sql += " ORDER BY aggregated_value DESC"
        return sql, params

    @classmethod
    def date_filter(cls, date_col: str, start: str | None = None, end: str | None = None) -> str:
        """Return a SQL WHERE fragment for date range filtering."""
        parts = []
        if start:
            parts.append(f"{date_col} >= :date_start")
        if end:
            parts.append(f"{date_col} <= :date_end")
        return " AND ".join(parts) if parts else ""

    @classmethod
    def date_filter_params(cls, start: str | None = None, end: str | None = None) -> dict:
        params: dict = {}
        if start:
            params["date_start"] = start
        if end:
            params["date_end"] = end
        return params
