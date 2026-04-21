from datetime import datetime


VALID_TASK_STATUSES = {"pending", "done"}
VALID_TASK_PRIORITIES = {"low", "medium", "high"}


def serialize_task(task):
    if not task:
        return task

    serialized_task = dict(task)

    if isinstance(serialized_task.get("created_at"), datetime):
        serialized_task["created_at"] = serialized_task["created_at"].isoformat()

    if isinstance(serialized_task.get("due_date"), datetime):
        serialized_task["due_date"] = serialized_task["due_date"].isoformat()

    if "user_id" in serialized_task and serialized_task["user_id"] is not None:
        try:
            serialized_task["user_id"] = int(serialized_task["user_id"])
        except Exception:
            pass

    return serialized_task


def parse_due_date(value):
    if value in [None, ""]:
        return None

    if isinstance(value, str):
        cleaned_value = value.strip()
        if not cleaned_value:
            return None

        cleaned_value = cleaned_value.replace("Z", "+00:00")
        return datetime.fromisoformat(cleaned_value)

    raise ValueError("due_date must be a valid ISO datetime string")


def normalize_task_priority(priority):
    normalized_priority = str(priority or "medium").strip().lower()

    if normalized_priority not in VALID_TASK_PRIORITIES:
        return "medium"

    return normalized_priority


def normalize_task_status(status):
    normalized_status = str(status or "pending").strip().lower()

    if normalized_status not in VALID_TASK_STATUSES:
        return "pending"

    return normalized_status


def validate_task_title(title):
    if title is None or not str(title).strip():
        raise ValueError("Title is required")

    return str(title).strip()


def validate_user_id(user_id):
    if user_id is None:
        raise ValueError("user_id is required")

    try:
        normalized_user_id = int(user_id)
    except Exception:
        raise ValueError("user_id must be a valid integer")

    if normalized_user_id <= 0:
        raise ValueError("user_id must be greater than zero")

    return normalized_user_id


def build_task_payload(title, description="", status="pending", priority="medium", due_date=None, user_id=None):
    return {
        "title": validate_task_title(title),
        "description": str(description or "").strip(),
        "status": normalize_task_status(status),
        "priority": normalize_task_priority(priority),
        "due_date": due_date,
        "user_id": validate_user_id(user_id)
    }