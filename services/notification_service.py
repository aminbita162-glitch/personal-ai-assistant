def build_notification_item(title, message, level="info"):
    return {
        "title": str(title or "").strip(),
        "message": str(message or "").strip(),
        "level": str(level or "info").strip().lower()
    }


def build_notifications_payload(notifications):
    return {
        "status": "success",
        "notifications": notifications or []
    }


def build_task_due_notification(task):
    return build_notification_item(
        title="Task reminder",
        message=f"{task.get('title', 'Task')} is due soon.",
        level="warning"
    )


def build_appointment_notification(appointment):
    return build_notification_item(
        title="Appointment reminder",
        message=f"{appointment.get('title', 'Appointment')} is coming up soon.",
        level="warning"
    )