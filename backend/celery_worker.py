import gevent.monkey
gevent.monkey.patch_all()

from app import create_app
from app.celery_app import make_celery

flask_app = create_app()
celery    = make_celery(flask_app)

# Import all task modules so Celery discovers them
import app.tasks.email_tasks          # noqa
import app.tasks.notification_tasks   # noqa
import app.tasks.diamond_tasks        # noqa
