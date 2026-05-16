from flask import request
from flask_socketio import emit, join_room, disconnect
from app.extensions import socketio
from app.sockets.chat import get_identity_from_token

@socketio.on("subscribe_notifications")
def on_subscribe_notifications(data):
    """
    Client joins their specific user room to receive notifications.
    data = { "token": "<jwt>" }
    """
    token = data.get("token")
    if not token:
        print("[DEBUG] subscribe_notifications: No token provided")
        return
        
    user_id, role = get_identity_from_token(token)
    print(f"[DEBUG] subscribe_notifications: user_id={user_id} role={role}")
    
    if not user_id:
        print("[DEBUG] subscribe_notifications: Token decode failed — user_id is None")
        emit("error", {"message": "Unauthorized for notifications"})
        return
        
    room = f"user_{user_id}"
    join_room(room)
    print(f"[DEBUG] subscribe_notifications: Joined room {room}")
