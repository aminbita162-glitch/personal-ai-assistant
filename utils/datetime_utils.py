from datetime import datetime, timedelta


def parse_iso_datetime(value, field_name="datetime"):
    if value in [None, ""]:
        return None

    if isinstance(value, str):
        cleaned_value = value.strip()
        if not cleaned_value:
            return None

        cleaned_value = cleaned_value.replace("Z", "+00:00")
        return datetime.fromisoformat(cleaned_value)

    raise ValueError(f"{field_name} must be a valid ISO datetime string")


def serialize_datetime(value):
    if isinstance(value, datetime):
        return value.isoformat()

    return value


def build_time_window(hours=1):
    current_time = datetime.utcnow()
    end_time = current_time + timedelta(hours=hours)

    return {
        "current_time": current_time,
        "end_time": end_time
    }