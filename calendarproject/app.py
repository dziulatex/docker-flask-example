from flask import Flask
from werkzeug.debug import DebuggedApplication
from werkzeug.middleware.proxy_fix import ProxyFix
from celery import Celery
from celery import Task
from calendarproject.extensions import db, debug_toolbar, flask_static_digest, init_login_manager,init_mail
from calendarproject.page.views import page
from calendarproject.up.views import up
from calendarproject.auth.views import auth
from calendarproject.calendar.views import calendar
from calendarproject.admin.views import admin
from calendarproject.models.user import User
from calendarproject.instructor.views import instructor
from calendarproject.notifications.views import notifications
import logging
from logging.handlers import RotatingFileHandler
import os


def setup_logging(app):
    # Create logs directory if it doesn't exist
    if not os.path.exists('logs'):
        os.mkdir('logs')

    # Set up file handler
    file_handler = RotatingFileHandler('logs/calendarproject.log', maxBytes=10240, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)

    # Set up console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # Add handlers to the app logger
    app.logger.addHandler(file_handler)
    app.logger.addHandler(console_handler)
    app.logger.setLevel(logging.INFO)

    app.logger.info('CalendarProject startup')
def create_celery_app(app=None):
    """
    Create a new Celery app and tie together the Celery config to the app's
    config. Wrap all tasks in the context of the application.

    :param app: Flask app
    :return: Celery app
    """
    app = app or create_app()

    class FlaskTask(Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery = Celery(app.import_name, task_cls=FlaskTask)
    celery.conf.update(app.config.get("CELERY_CONFIG", {}))
    celery.set_default()
    app.extensions["celery"] = celery

    return celery


def create_app(settings_override=None):
    """
    Create a Flask application using the app factory pattern.
    """
    app = Flask(__name__, static_folder="../public", static_url_path="")

    app.config.from_object("config.settings")

    if settings_override:
        app.config.update(settings_override)

    middleware(app)

    app.register_blueprint(up)
    app.register_blueprint(page)
    app.register_blueprint(auth)
    app.register_blueprint(notifications)
    app.register_blueprint(calendar)
    app.register_blueprint(admin)
    app.register_blueprint(instructor)
    extensions(app)
    setup_logging(app)
    with app.app_context():
        db.create_all()
        create_instructor_if_not_exists(app)

    return app


def extensions(app):
    """
    Register 0 or more extensions (mutates the app passed in).
    """
    debug_toolbar.init_app(app)
    db.init_app(app)
    flask_static_digest.init_app(app)
    init_login_manager(app)
    init_mail(app)
    return None


def middleware(app):
    """
    Register 0 or more middleware (mutates the app passed in).
    """
    # Enable the Flask interactive debugger in the browser for development.
    if app.debug:
        app.wsgi_app = DebuggedApplication(app.wsgi_app, evalex=True)

    # Set the real IP address into request.remote_addr when behind a proxy.
    app.wsgi_app = ProxyFix(app.wsgi_app)

    return None


def create_instructor_if_not_exists(app):
    """
    Create an instructor account if it doesn't exist.
    """
    with app.app_context():
        instructor = User.query.filter_by(is_instructor=True).first()
        if not instructor:
            new_instructor = User(
                username="instructor",
                email="instructor@example.com",
                first_name="Jacek",  # Dodane imię
                last_name="Jeleń",    # Dodane nazwisko
                is_instructor=True
            )
            new_instructor.set_password("password")  # W środowisku produkcyjnym należy użyć bezpieczniejszego hasła
            db.session.add(new_instructor)
            db.session.commit()
            print("Konto instruktora zostało utworzone.")
        else:
            print("Konto instruktora już istnieje.")


celery_app = create_celery_app()