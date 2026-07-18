def split_terms(query: str) -> list[str]:
    return [t for t in query.lower().split() if t]
