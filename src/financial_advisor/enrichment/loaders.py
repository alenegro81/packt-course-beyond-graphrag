"""Loaders for structured data sources: public registries, news feeds, executive databases."""


def load_executives(company_id: str) -> list[dict]:
    """Return executive records for a company from a public registry or reference list."""
    raise NotImplementedError


def load_news(company_id: str, start_date: str, end_date: str) -> list[dict]:
    """Return news articles for a company within the given date range."""
    raise NotImplementedError
