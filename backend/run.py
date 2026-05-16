import gevent.monkey
gevent.monkey.patch_all()

from app import create_app
from app.extensions import socketio

app = create_app()

if __name__ == "__main__":
    socketio.run(app, debug=True, port=5000, host="0.0.0.0")
