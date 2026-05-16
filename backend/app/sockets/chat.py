from flask import request
from flask_socketio import emit, join_room, leave_room, disconnect
from flask_jwt_extended import decode_token
from datetime import datetime

from app.extensions import socketio, get_db
from app.utils.helpers import oid


# ── Helpers ───────────────────────────────────────────────

def _decode(token):
    """Return identity dict from JWT or None."""
    if not token:
        print("[DEBUG] _decode: No token provided")
        return None
    try:
        decoded = decode_token(token)
        return {"id": decoded["sub"], "role": decoded.get("role")}
    except Exception as e:
        print(f"[ERROR] _decode: JWT decode failed: {e}")
        return None

def get_identity_from_token(token):
    """Legacy helper for app.sockets.notifications"""
    identity = _decode(token)
    if identity:
        return identity["id"], identity["role"]
    return None, None


def _can_join(identity, thread):
    """
    Returns True if the identity is permitted to join this thread.

    Thread A — Student ↔ Admin only.
    Thread B — Expert  ↔ Admin only.
    Employees and super_admins may join either.
    """
    role     = identity["role"]
    user_oid = oid(identity["id"])
    t_type   = thread.get("thread_type")

    if role in ("employee", "super_admin"):
        return True

    if role == "student":
        # Need to fetch student _id based on user_id to compare with thread.student_id
        db = get_db()
        print(f"[DEBUG] _can_join: Checking student auth for user {user_oid} on thread type={t_type}")
        student_prof = db.students.find_one({"user_id": user_oid})
        if not student_prof:
            print(f"[DEBUG] _can_join: No student profile found for user {user_oid}")
            return False
        result = (
            t_type == "A"
            and thread.get("student_id") == student_prof["_id"]
        )
        if not result:
            print(f"[DEBUG] _can_join: Student {user_oid} not authorized — thread.student_id={thread.get('student_id')} profile._id={student_prof['_id']} t_type={t_type}")
        return result

    if role == "expert":
        db = get_db()
        print(f"[DEBUG] _can_join: Checking expert auth for user {user_oid} on thread type={t_type}")
        expert_prof = db.experts.find_one({"user_id": user_oid})
        if not expert_prof:
            print(f"[DEBUG] _can_join: No expert profile found for user {user_oid}")
            return False
        result = (
            t_type == "B"
            and thread.get("expert_id") == expert_prof["_id"]
        )
        if not result:
            print(f"[DEBUG] _can_join: Expert {user_oid} not authorized — thread.expert_id={thread.get('expert_id')} profile._id={expert_prof['_id']} t_type={t_type}")
        return result

    print(f"[DEBUG] _can_join: Unknown role '{role}' denied access")
    return False


# ── Connection ────────────────────────────────────────────

@socketio.on("connect")
def on_connect(auth):
    """
    Client must pass JWT in the auth dict:
      const socket = io(SERVER_URL, { auth: { token: "..." } })

    On connect we verify the token and register the user's personal
    notification room immediately so they receive notifications even
    before they join a thread room.
    """
    identity = _decode((auth or {}).get("token"))
    if not identity:
        print("[DEBUG] Socket connection rejected: invalid token")
        return False  # Reject connection

    print(f"[DEBUG] Socket connected: {identity['id']} ({identity['role']})")

    # Personal notification room — used by notification_service.py
    personal_room = f"user_{identity['id']}"
    join_room(personal_room)

    emit("connected", {
        "user_id": identity["id"],
        "role":    identity["role"],
    })


@socketio.on("disconnect")
def on_disconnect():
    print(f"[DEBUG] Socket disconnected: sid={request.sid}")
    # Flask-SocketIO auto-cleans rooms on disconnect


# ── Thread rooms ──────────────────────────────────────────

@socketio.on("join_thread")
def on_join(data):
    """
    Join a specific chat thread room and receive message history.

    Client sends:
      { thread_id: "<id>", token: "<jwt>" }
    """
    thread_id = (data or {}).get("thread_id")
    token     = (data or {}).get("token")
    identity  = _decode(token)

    if not thread_id or not identity:
        print(f"[DEBUG] join_thread: Rejected — thread_id={thread_id!r} identity={identity}")
        emit("error", {"code": "AUTH_REQUIRED", "message": "Invalid token or missing thread_id"}, to=request.sid)
        return

    print(f"[DEBUG] User {identity['id']} ({identity['role']}) joining thread {thread_id}")

    print(f"[DEBUG] join_thread: User {identity['id']} ({identity['role']}) joining thread {thread_id}")

    print(f"[DEBUG] join_thread: Fetching thread {thread_id} from DB")
    db     = get_db()
    try:
        thread = db.threads.find_one({"_id": oid(thread_id)})
        print(f"[DEBUG] join_thread: Successfully fetched thread {thread_id}")
    except Exception as e:
        print(f"[ERROR] join_thread: DB error finding thread {thread_id}: {e}")
        emit("error", {"code": "DB_ERROR", "message": "Internal error"}, to=request.sid)
        return

    if not thread:
        print(f"[DEBUG] Join failed: Thread {thread_id} not found")
        emit("error", {"code": "NOT_FOUND", "message": "Thread not found"}, to=request.sid)
        return

    if not _can_join(identity, thread):
        print(f"[DEBUG] Join failed: User {identity['id']} not authorized for thread {thread_id}")
        emit("error", {"code": "FORBIDDEN", "message": "Not authorized for this thread"}, to=request.sid)
        return

    room = f"thread_{thread_id}"
    join_room(room)
    print(f"[DEBUG] User joined room {room}")

    print(f"[DEBUG] join_thread: Fetching messages for thread {thread_id} from DB")
    try:
        messages = list(
            db.messages
              .find({"thread_id": oid(thread_id)})
              .sort("created_at", 1)
              .limit(100)
        )
        print(f"[DEBUG] join_thread: Successfully fetched {len(messages)} messages for thread {thread_id}")
    except Exception as e:
        print(f"[ERROR] join_thread: DB error fetching messages for thread {thread_id}: {e}")
        emit("error", {"code": "DB_ERROR", "message": "Internal error fetching messages"}, to=request.sid)
        return
    
    # Send historical messages. We use event name matching the thread_id
    # for the admin cockpit routing, or just "message_history"
    history_payload = []
    for m in messages:
        dt = m.get("created_at")
        history_payload.append({
            "_id":            str(m["_id"]),
            "sender_user_id": str(m["sender_user_id"]),
            "body":           m["body"],
            "created_at":     dt.isoformat() if hasattr(dt, 'isoformat') else str(dt),
        })
    
    print(f"[DEBUG] Emitting {len(history_payload)} messages for thread {thread_id}")
    emit(f"message_history_{thread_id}", history_payload, to=request.sid)

    emit("joined", {"thread_id": thread_id, "room": room}, to=request.sid)


@socketio.on("send_message")
def on_send_message(data):
    """
    Persist a message and broadcast it to the room.

    Client sends:
      { thread_id: "<id>", body: "text", token: "<jwt>" }
    """
    thread_id = (data or {}).get("thread_id")
    body      = ((data or {}).get("body") or "").strip()
    token     = (data or {}).get("token")
    identity  = _decode(token)

    print(f"[DEBUG] Sending message to thread {thread_id} from {identity.get('id') if identity else 'unknown'}")
    
    if not thread_id or not body or not identity:
        emit("error", {"code": "INVALID", "message": "thread_id, body, and token are required"}, to=request.sid)
        return

    print(f"[DEBUG] send_message: Fetching thread {thread_id} from DB")
    db     = get_db()
    try:
        thread = db.threads.find_one({"_id": oid(thread_id)})
        print(f"[DEBUG] send_message: Fetched thread {thread_id}")
    except Exception as e:
        print(f"[ERROR] send_message: DB error finding thread {thread_id}: {e}")
        emit("error", {"code": "DB_ERROR", "message": "Internal error"}, to=request.sid)
        return

    if not thread or not _can_join(identity, thread):
        emit("error", {"code": "FORBIDDEN", "message": "Cannot send to this thread"}, to=request.sid)
        return

    # Persist
    result = db.messages.insert_one({
        "thread_id":      oid(thread_id),
        "sender_user_id": oid(identity["id"]),
        "body":           body,
        "created_at":     datetime.utcnow(),
    })
    
    print(f"[DEBUG] Message inserted with id {result.inserted_id}")

    payload = {
        "_id":            str(result.inserted_id),
        "thread_id":      thread_id,
        "sender_user_id": identity["id"],
        "sender_role":    identity["role"],
        "body":           body,
        "created_at":     datetime.utcnow().isoformat(),
    }

    # Broadcast to everyone in the room (including sender, for echo confirmation)
    emit("new_message", payload, room=f"thread_{thread_id}")

    # Trigger notification for the other participant(s)
    _notify_other_participants(thread, identity, body, db)


@socketio.on("leave_thread")
def on_leave(data):
    thread_id = (data or {}).get("thread_id")
    if thread_id:
        leave_room(f"thread_{thread_id}")


# ── Notification trigger ──────────────────────────────────

def _notify_other_participants(thread, sender_identity, body, db):
    """
    Emit a lightweight notification event to the other side of the thread.
    This uses the personal room (user_<id>) which the recipient joined on connect.
    """
    sender_oid = oid(sender_identity["id"])
    t_type     = thread.get("thread_type")
    recipients = []
    print(f"[DEBUG] _notify_other_participants: thread={thread['_id']} type={t_type} sender={sender_identity['id']}")

    if t_type == "A":
        # Thread A: Student ↔ Admin
        if thread.get("student_id"):
            student = db.students.find_one({"_id": thread["student_id"]}, {"user_id": 1})
            if student and student["user_id"] != sender_oid:
                recipients.append(str(student["user_id"]))
            elif student:
                print(f"[DEBUG] _notify_other_participants: Skipping student (is sender)")
        if thread.get("employee_id"):
            employee = db.employees.find_one({"_id": thread["employee_id"]}, {"user_id": 1})
            if employee and employee["user_id"] != sender_oid:
                recipients.append(str(employee["user_id"]))
            elif employee:
                print(f"[DEBUG] _notify_other_participants: Skipping employee (is sender)")
    else:
        # Thread B: Expert ↔ Admin
        if thread.get("expert_id"):
            expert = db.experts.find_one({"_id": thread["expert_id"]}, {"user_id": 1})
            if expert and expert["user_id"] != sender_oid:
                recipients.append(str(expert["user_id"]))
            elif expert:
                print(f"[DEBUG] _notify_other_participants: Skipping expert (is sender)")
        if thread.get("employee_id"):
            employee = db.employees.find_one({"_id": thread["employee_id"]}, {"user_id": 1})
            if employee and employee["user_id"] != sender_oid:
                recipients.append(str(employee["user_id"]))
            elif employee:
                print(f"[DEBUG] _notify_other_participants: Skipping employee (is sender)")

    print(f"[DEBUG] _notify_other_participants: Notifying {len(recipients)} recipients: {recipients}")
    for uid in recipients:
        print(f"[DEBUG] _notify_other_participants: Emitting to room user_{uid}")
        try:
            # Emit to that user's personal room — works cross-process via Redis message_queue
            socketio.emit(
                "notification",
                {
                    "type":      "new_message",
                    "thread_id": str(thread["_id"]),
                    "preview":   body[:60] + ("…" if len(body) > 60 else ""),
                },
                room=f"user_{uid}",
            )
            print(f"[DEBUG] _notify_other_participants: Emitted to user_{uid} OK")
        except Exception as e:
            print(f"[ERROR] _notify_other_participants: socketio.emit to user_{uid} FAILED: {e}")
