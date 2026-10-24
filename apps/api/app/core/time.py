from datetime import datetime, timezone


def utc(value: datetime) -> datetime:
    """SQLite stores our UTC timestamps without offsets; PostgreSQL preserves offsets."""
    return (
        value.replace(tzinfo=timezone.utc)
        if value.tzinfo is None
        else value.astimezone(timezone.utc)
    )
