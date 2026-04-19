def validate_required_string(value, field_name):
    if value is None or not str(value).strip():
        raise ValueError(f"{field_name} is required")

    return str(value).strip()


def validate_status(value, allowed_values):
    if value is None:
        raise ValueError("status is required")

    cleaned_value = str(value).strip().lower()

    if cleaned_value not in allowed_values:
        raise ValueError(f"status must be one of: {', '.join(allowed_values)}")

    return cleaned_value


def validate_priority(value):
    allowed_values = ["low", "medium", "high"]

    if value is None:
        return "medium"

    cleaned_value = str(value).strip().lower()

    if cleaned_value not in allowed_values:
        return "medium"

    return cleaned_value