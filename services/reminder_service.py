from datetime import datetime, timedelta


def serialize_reminder_item(item, time_field):
    if not item:
        return item

    serialized_item = dict(item)

    if isinstance(serialized_item.get(time_field), datetime):
        serialized_item[time_field] = serialized_item[time_field].isoformat()

    return serialized_item


def build_reminder_window(hours=1):
    current_time = datetime.utcnow()
    end_time = current_time + timedelta(hours=hours)

    return {
        "current_time": current_time,
        "end_time": end_time
    }


def build_reminders_payload(tasks, appointments):
    serialized_tasks = [
        serialize_reminder_item(task, "due_date")
        for task in (tasks or [])
    ]

    serialized_appointments = [
        serialize_reminder_item(appointment, "appointment_time")
        for appointment in (appointments or [])
    ]

    return {
        "status": "success",
        "tasks": serialized_tasks,
        "appointments": serialized_appointments
    }