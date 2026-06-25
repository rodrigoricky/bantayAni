import uuid
from datetime import datetime

from utils.database import (
    execute_query,
    is_demo_mode,
    get_demo_notifications,
    add_demo_notification,
    update_demo_notification,
    _load_demo_data,
)


def create_notification(
    user_id: str,
    notification_type: str,
    title: str,
    message: str,
    claim_id: str | None = None,
) -> dict:
    """Create a notification for a specific user."""
    if is_demo_mode():
        notification = {
            "id": str(uuid.uuid4()),
            "user_id": str(user_id),
            "type": notification_type,
            "title": title,
            "message": message,
            "claim_id": str(claim_id) if claim_id else None,
            "is_read": False,
            "created_at": datetime.utcnow().isoformat() + "Z",
        }
        add_demo_notification(notification)
        return notification

    result = execute_query(
        """
        INSERT INTO notifications (user_id, type, title, message, claim_id)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING *
        """,
        (user_id, notification_type, title, message, claim_id),
        fetch_one=True,
    )
    return _format_notification(result) if result else {}


def _get_mao_users_for_municipality(municipality_id: str) -> list[dict]:
    if is_demo_mode():
        data = _load_demo_data()
        return [
            u for u in data.get("users", [])
            if u.get("role") == "MAO" and u.get("municipality_id") == municipality_id
        ]

    users = execute_query(
        """
        SELECT id, email, role, municipality_id
        FROM users
        WHERE role = 'MAO' AND municipality_id = %s
        """,
        (municipality_id,),
        fetch_all=True,
    )
    return users or []


def notify_mao_claim_status_change(
    claim_id: str,
    claim_number: str,
    farmer_name: str,
    status: str,
    municipality_id: str,
    reason: str | None = None,
) -> list[dict]:
    """Notify all MAO users in a municipality when PCIC updates a claim decision."""
    status_upper = status.upper()
    type_map = {
        "APPROVED": "CLAIM_APPROVED",
        "REJECTED": "CLAIM_REJECTED",
        "FLAGGED": "CLAIM_FLAGGED",
    }
    title_map = {
        "APPROVED": f"Claim approved: {claim_number}",
        "REJECTED": f"Claim rejected: {claim_number}",
        "FLAGGED": f"Claim flagged: {claim_number}",
    }
    message_map = {
        "APPROVED": f"PCIC approved the claim for {farmer_name} ({claim_number}).",
        "REJECTED": f"PCIC rejected the claim for {farmer_name} ({claim_number})."
        + (f" Reason: {reason}" if reason else ""),
        "FLAGGED": f"PCIC flagged the claim for {farmer_name} ({claim_number})."
        + (f" Reason: {reason}" if reason else ""),
    }

    notification_type = type_map.get(status_upper)
    if not notification_type or not municipality_id:
        return []

    mao_users = _get_mao_users_for_municipality(municipality_id)
    created = []
    for user in mao_users:
        notification = create_notification(
            user_id=str(user["id"]),
            notification_type=notification_type,
            title=title_map[status_upper],
            message=message_map[status_upper],
            claim_id=claim_id,
        )
        if notification:
            created.append(notification)
    return created


def _format_notification(row: dict) -> dict:
    if not row:
        return {}
    created_at = row.get("created_at")
    if created_at and hasattr(created_at, "isoformat"):
        created_at = created_at.isoformat()
    return {
        "id": str(row["id"]),
        "user_id": str(row["user_id"]),
        "type": row.get("type"),
        "title": row.get("title"),
        "message": row.get("message"),
        "claim_id": str(row["claim_id"]) if row.get("claim_id") else None,
        "is_read": bool(row.get("is_read", False)),
        "created_at": str(created_at) if created_at else None,
    }


def get_notifications_for_user(user_id: str) -> dict:
    """Return notifications and unread count for the authenticated user."""
    if is_demo_mode():
        notifications = [
            _format_notification(n)
            for n in get_demo_notifications()
            if str(n.get("user_id")) == str(user_id)
        ]
        notifications.sort(key=lambda n: n.get("created_at") or "", reverse=True)
        unread_count = sum(1 for n in notifications if not n.get("is_read"))
        return {"notifications": notifications, "unread_count": unread_count}

    rows = execute_query(
        """
        SELECT * FROM notifications
        WHERE user_id = %s
        ORDER BY created_at DESC
        LIMIT 50
        """,
        (user_id,),
        fetch_all=True,
    )
    notifications = [_format_notification(row) for row in (rows or [])]
    count_result = execute_query(
        """
        SELECT COUNT(*) AS count FROM notifications
        WHERE user_id = %s AND is_read = FALSE
        """,
        (user_id,),
        fetch_one=True,
    )
    unread_count = int(count_result["count"]) if count_result else 0
    return {"notifications": notifications, "unread_count": unread_count}


def _get_pcic_users() -> list[dict]:
    if is_demo_mode():
        data = _load_demo_data()
        return [u for u in data.get("users", []) if u.get("role") == "PCIC"]

    users = execute_query(
        "SELECT id, email, role FROM users WHERE role = 'PCIC'",
        fetch_all=True,
    )
    return users or []


def _get_regional_users() -> list[dict]:
    if is_demo_mode():
        data = _load_demo_data()
        return [u for u in data.get("users", []) if u.get("role") == "DA_REGIONAL"]

    users = execute_query(
        "SELECT id, email, role FROM users WHERE role = 'DA_REGIONAL'",
        fetch_all=True,
    )
    return users or []


def notify_pcic_new_claim(
    claim_id: str,
    claim_number: str,
    farmer_name: str,
    municipality_name: str,
) -> list[dict]:
    """Notify PCIC users when an MAO submits a new claim."""
    created = []
    for user in _get_pcic_users():
        notification = create_notification(
            user_id=str(user["id"]),
            notification_type="CLAIM_SUBMITTED",
            title=f"New claim submitted: {claim_number}",
            message=f"{farmer_name} ({municipality_name}) — claim {claim_number} is awaiting PCIC review.",
            claim_id=claim_id,
        )
        if notification:
            created.append(notification)
    return created


def notify_regional_critical_farm(
    farm_id: str,
    farmer_name: str,
    municipality_name: str,
    ndvi: float,
) -> list[dict]:
    """Notify DA Regional users when a farm enters critical NDVI status."""
    created = []
    for user in _get_regional_users():
        notification = create_notification(
            user_id=str(user["id"]),
            notification_type="CRITICAL_FARM_ALERT",
            title=f"Critical farm alert: {municipality_name}",
            message=(
                f"{farmer_name} ({farm_id}) entered CRITICAL status "
                f"with NDVI {ndvi:.3f}. Immediate review recommended."
            ),
            claim_id=None,
        )
        if notification:
            created.append(notification)
    return created


def mark_notification_read(notification_id: str, user_id: str) -> dict | None:
    """Mark a single notification as read for the given user."""
    if is_demo_mode():
        notifications = get_demo_notifications()
        for notification in notifications:
            if (
                str(notification.get("id")) == str(notification_id)
                and str(notification.get("user_id")) == str(user_id)
            ):
                updated = update_demo_notification(notification_id, {"is_read": True})
                return _format_notification(updated) if updated else None
        return None

    result = execute_query(
        """
        UPDATE notifications
        SET is_read = TRUE
        WHERE id = %s AND user_id = %s
        RETURNING *
        """,
        (notification_id, user_id),
        fetch_one=True,
    )
    return _format_notification(result) if result else None