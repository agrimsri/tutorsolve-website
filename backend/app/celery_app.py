from celery import Celery

def make_celery(app):
    celery = Celery(app.import_name)

    celery.conf.update(
        broker_url             = app.config["CELERY_BROKER_URL"],
        result_backend         = app.config["CELERY_RESULT_BACKEND"],
        task_serializer        = app.config["CELERY_TASK_SERIALIZER"],
        result_serializer      = app.config["CELERY_RESULT_SERIALIZER"],
        accept_content         = app.config["CELERY_ACCEPT_CONTENT"],
        timezone               = app.config["CELERY_TIMEZONE"],
        enable_utc             = app.config["CELERY_ENABLE_UTC"],
        worker_concurrency     = 4,
        worker_pool            = "gevent",
        task_track_started     = True,
        task_acks_late         = True,
        task_reject_on_worker_lost = True,
        # Periodic tasks (Celery beat)
        beat_schedule={
            "prune-old-notifications-hourly": {
                "task":     "app.tasks.notification_tasks.prune_old_notifications",
                "schedule": 3600,   # every 3600 seconds = 1 hour
            },
            "broadcast-pending-questions": {
                "task":     "app.tasks.diamond_tasks.broadcast_pending_questions",
                "schedule": 300,    # every 5 mins
            },
        },
    )

    # Make tasks run in Flask app context
    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery
