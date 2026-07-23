import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

TABLE_SCHEMAS = {
    "sales": {
        "columns": [
            "id",
            "date",
            "region",
            "product_category",
            "product_name",
            "quantity",
            "unit_price",
            "total_revenue",
            "cost",
            "profit",
            "customer_segment",
        ],
        "description": (
            "Sales transactions with date, region, product info, revenue, cost, profit, and customer segment"
        ),
    },
    "customers": {
        "columns": ["id", "name", "email", "region", "signup_date", "lifetime_value", "orders_count", "segment"],
        "description": "Customer profiles with lifetime value, order count, region, and segment",
    },
    "website_analytics": {
        "columns": [
            "id",
            "date",
            "page_views",
            "unique_visitors",
            "bounce_rate",
            "avg_session_duration",
            "conversions",
            "revenue",
        ],
        "description": (
            "Daily website metrics including page views, visitors,"
            " bounce rate, session duration, conversions, and revenue"
        ),
    },
}

DANGEROUS_SQL_RE = re.compile(
    r"(;|\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|EXEC|EXECUTE|INTO|GRANT|REVOKE)\b)",
    re.IGNORECASE,
)


class NLQueryEngine:
    """Natural language to SQL conversion engine."""

    INTENT_PATTERNS = {
        "show_revenue": {
            "patterns": [
                r"(?:show|get|display|find|calculate|what is|what's)\s+(?:the\s+)?(?:total\s+)?revenue",
                r"revenue\s+(?:by|for|from|per|in)",
                r"(?:total|sum|aggregate)\s+revenue",
                r"how much.*(?:made|earned|revenue|sales)",
            ],
            "template": (
                "SELECT {group}, SUM(total_revenue) AS total_revenue"
                " FROM sales {where} GROUP BY {group}"
                " ORDER BY total_revenue DESC"
            ),
            "default_group": "region",
        },
        "show_profit": {
            "patterns": [
                r"(?:show|get|display|find|calculate)\s+(?:the\s+)?(?:total\s+)?profit",
                r"profit\s+(?:by|for|from|per|in)",
                r"(?:total|sum)\s+profit",
            ],
            "template": (
                "SELECT {group}, SUM(profit) AS total_profit"
                " FROM sales {where} GROUP BY {group}"
                " ORDER BY total_profit DESC"
            ),
            "default_group": "region",
        },
        "show_customers": {
            "patterns": [
                r"(?:show|get|display|list|how many)\s+(?:the\s+)?(?:total\s+)?customers",
                r"customer\s+(?:count|number|total|list)",
                r"how many\s+customers",
            ],
            "template": (
                "SELECT COUNT(*) AS total_customers,"
                " AVG(lifetime_value) AS avg_ltv,"
                " SUM(lifetime_value) AS total_ltv"
                " FROM customers {where}"
            ),
            "default_group": None,
        },
        "show_products": {
            "patterns": [
                r"(?:show|get|display|list)\s+(?:the\s+)?(?:top|best|most)\s+\w*\s*products?",
                r"(?:top|best|most)\s+\w*\s+products?\s+(?:by|for)",
                r"product\s+performance",
            ],
            "template": (
                "SELECT product_name, product_category,"
                " SUM(total_revenue) AS revenue,"
                " SUM(profit) AS profit,"
                " SUM(quantity) AS quantity"
                " FROM sales {where}"
                " GROUP BY product_name, product_category"
                " ORDER BY revenue DESC LIMIT 10"
            ),
            "default_group": None,
        },
        "show_website": {
            "patterns": [
                r"(?:show|get|display)\s+(?:the\s+)?(?:website|web|site)\s+(?:stats|analytics|metrics|data)",
                r"website\s+(?:traffic|performance|analytics)",
                r"(?:page\s+views|visitors|conversions|bounce\s+rate)",
            ],
            "template": (
                "SELECT SUM(page_views) AS total_page_views,"
                " SUM(unique_visitors) AS total_visitors,"
                " AVG(bounce_rate) AS avg_bounce_rate,"
                " SUM(conversions) AS total_conversions,"
                " SUM(revenue) AS total_revenue"
                " FROM website_analytics {where}"
            ),
            "default_group": None,
        },
        "show_trends": {
            "patterns": [
                r"(?:show|get|display)\s+(?:the\s+)?(?:revenue\s+)?trends?",
                r"(?:monthly|weekly|daily)\s+(?:revenue|sales|trend)",
                r"revenue\s+over\s+time",
            ],
            "template": (
                "SELECT SUBSTR(date, 1, 7) AS month,"
                " SUM(total_revenue) AS revenue,"
                " SUM(profit) AS profit,"
                " SUM(quantity) AS quantity"
                " FROM sales {where}"
                " GROUP BY SUBSTR(date, 1, 7)"
                " ORDER BY month"
            ),
            "default_group": None,
        },
        "show_regions": {
            "patterns": [
                r"(?:show|get|display)\s+(?:the\s+)?(?:revenue\s+)?by\s+region",
                r"regional\s+(?:breakdown|comparison|performance|revenue)",
                r"(?:which|what)\s+region",
            ],
            "template": (
                "SELECT region,"
                " SUM(total_revenue) AS revenue,"
                " SUM(profit) AS profit,"
                " COUNT(*) AS orders"
                " FROM sales {where}"
                " GROUP BY region"
                " ORDER BY revenue DESC"
            ),
            "default_group": None,
        },
    }

    FILTER_KEYWORDS = {
        "region": ["north", "south", "east", "west"],
        "product_category": ["electronics", "clothing", "food", "furniture"],
        "customer_segment": ["enterprise", "smb", "consumer"],
    }

    @classmethod
    def nl_to_sql(cls, query: str) -> dict[str, Any]:
        query_lower = query.lower().strip()

        best_intent = None
        best_score = 0
        for intent_name, intent in cls.INTENT_PATTERNS.items():
            for pattern in intent["patterns"]:
                if re.search(pattern, query_lower):
                    score = len(re.search(pattern, query_lower).group())
                    if score > best_score:
                        best_score = score
                        best_intent = intent_name

        if not best_intent:
            return {
                "sql": None,
                "intent": "unknown",
                "explanation": (
                    "I couldn't understand the query. Try asking about"
                    " revenue, profit, customers, products,"
                    " website analytics, trends, or regions."
                ),
                "error": "Unrecognized intent",
            }

        intent = cls.INTENT_PATTERNS[best_intent]

        group = intent["default_group"]
        for group_col in ["region", "product_category", "customer_segment", "product_name"]:
            if group_col in query_lower:
                group = group_col
                break

        where_parts = []
        for filter_col, keywords in cls.FILTER_KEYWORDS.items():
            for kw in keywords:
                if kw in query_lower:
                    where_parts.append(f"{filter_col} = '{kw.title()}'")
                    break

        where_clause = ""
        if where_parts:
            where_clause = "WHERE " + " AND ".join(where_parts)

        sql = intent["template"].format(
            group=group or "region",
            where=where_clause,
        )

        if DANGEROUS_SQL_RE.search(sql):
            return {"sql": None, "error": "Generated query contains disallowed operations"}

        return {
            "sql": sql,
            "intent": best_intent,
            "explanation": f"Generated SQL for: {best_intent.replace('_', ' ')}",
            "filters_applied": where_parts if where_parts else None,
        }

    @classmethod
    def get_schema_help(cls) -> str:
        help_text = "Available tables and columns:\n\n"
        for table, info in TABLE_SCHEMAS.items():
            help_text += f"Table: {table}\n"
            help_text += f"  Description: {info['description']}\n"
            help_text += f"  Columns: {', '.join(info['columns'])}\n\n"
        help_text += "Example queries:\n"
        help_text += "- Show total revenue by region\n"
        help_text += "- What is the profit for electronics?\n"
        help_text += "- How many enterprise customers are there?\n"
        help_text += "- Show top products by revenue\n"
        help_text += "- Website analytics for last month\n"
        help_text += "- Revenue trends monthly\n"
        help_text += "- Revenue in the North region\n"
        return help_text
