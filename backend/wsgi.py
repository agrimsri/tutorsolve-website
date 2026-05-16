import gevent.monkey
gevent.monkey.patch_all()

from app import create_app
from app.extensions import socketio

app = create_app()
