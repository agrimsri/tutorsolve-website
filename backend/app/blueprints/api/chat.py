from flask import request, jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from datetime import datetime

from app.blueprints.api import api_bp
from app.extensions import get_db, socketio
from app.utils.helpers import oid


from app.utils.decorators import role_required
from app.utils.constants import Role

@api_bp.route("/chat/<thread_id>/messages", methods=["GET"])
@role_required(Role.STUDENT, Role.EXPERT, Role.EMPLOYEE, Role.SUPER_ADMIN)
def get_messages(thread_id):
    db       = get_db()
    messages = list(db.messages.find({"thread_id": oid(thread_id)}).sort("created_at", 1))
    return jsonify([{
        "_id":            str(m["_id"]),
        "sender_user_id": str(m["sender_user_id"]),
        "body":           m["body"],
        "created_at":     str(m["created_at"])
    } for m in messages]), 200


@api_bp.route("/chat/<thread_id>/messages", methods=["POST"])
@role_required(Role.STUDENT, Role.EXPERT, Role.EMPLOYEE, Role.SUPER_ADMIN)
def post_message(thread_id):
    uid    = get_jwt_identity()
    data   = request.get_json()
    db     = get_db()
    
    now = datetime.utcnow()
    result = db.messages.insert_one({
        "thread_id":      oid(thread_id),
        "sender_user_id": oid(uid),
        "body":           data["body"],
        "created_at":     now
    })

    # Emit socket event so UI updates for everyone in the room
    message = {
        "_id":            str(result.inserted_id),
        "thread_id":      str(thread_id),
        "sender_user_id": str(uid),
        "body":           data["body"],
        "created_at":     now.isoformat()
    }
    # Emit via start_background_task to avoid deadlocking the PubSub subscriber
    # greenlet in gevent mode. Never call socketio.emit() directly from an HTTP
    # request handler — even with message_queue configured, it races with the
    # subscriber greenlet for the SocketIO server's internal lock, silently
    # killing all socket delivery until restart.
    _message = message
    _room    = f"thread_{thread_id}"
    socketio.start_background_task(lambda: socketio.emit("new_message", _message, room=_room))

    return jsonify({"_id": str(result.inserted_id)}), 201
