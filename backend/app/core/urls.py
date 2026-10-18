def actor_url(actor_id: int, tab: str | None = None) -> str:
    if tab:
        return f"/actors/{actor_id}?tab={tab}"
    return f"/actors/{actor_id}"
