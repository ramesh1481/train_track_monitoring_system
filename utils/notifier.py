from datetime import datetime
import sqlite3


def record_alert(db_path, complaint_id, channel, recipient, message):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO alerts (complaint_id, channel, recipient, message, sent_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            complaint_id,
            channel,
            recipient,
            message,
            datetime.now().strftime("%Y%m%d_%H%M%S"),
        ),
    )
    conn.commit()
    conn.close()


def notify_high_severity(db_path, complaint_id, severity, location):
    if severity != "HIGH":
        return

    message = f"HIGH severity track crack detected at {location or 'Unknown location'}."
    # Placeholder channels. Replace recipient with real email/phone in production.
    record_alert(db_path, complaint_id, "email", "maintenance@example.com", message)
    record_alert(db_path, complaint_id, "whatsapp", "+918778496183", message)
