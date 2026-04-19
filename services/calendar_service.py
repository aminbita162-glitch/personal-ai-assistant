from datetime import datetime


VALID_APPOINTMENT_STATUSES = {"scheduled", "done", "cancelled"}


def serialize_appointment(appointment):
    if not appointment:
        return appointment

    serialized_appointment = dict(appointment)

    if isinstance(serialized_appointment.get("appointment_time"), datetime):
        serialized_appointment["appointment_time"] = serialized_appointment["appointment_time"].isoformat()

    if isinstance(serialized_appointment.get("created_at"), datetime):
        serialized_appointment["created_at"] = serialized_appointment["created_at"].isoformat()

    return serialized_appointment


def parse_appointment_time(value):
    if value in [None, ""]:
        return None

    if isinstance(value, str):
        cleaned_value = value.strip()
        if not cleaned_value:
            return None

        cleaned_value = cleaned_value.replace("Z", "+00:00")
        return datetime.fromisoformat(cleaned_value)

    raise ValueError("appointment_time must be a valid ISO datetime string")


def normalize_appointment_status(status):
    normalized_status = str(status or "scheduled").strip().lower()

    if normalized_status not in VALID_APPOINTMENT_STATUSES:
        return "scheduled"

    return normalized_status


def validate_appointment_title(title):
    if title is None or not str(title).strip():
        raise ValueError("Title is required")

    return str(title).strip()


def validate_appointment_time(appointment_time):
    if not appointment_time:
        raise ValueError("appointment_time is required")

    return appointment_time


def build_appointment_payload(
    title,
    appointment_time,
    description="",
    location="",
    status="scheduled"
):
    normalized_appointment_time = validate_appointment_time(appointment_time)

    return {
        "title": validate_appointment_title(title),
        "description": str(description or "").strip(),
        "appointment_time": normalized_appointment_time,
        "location": str(location or "").strip(),
        "status": normalize_appointment_status(status)
    }