import logging
import os
import sys

import flask

from albumlistbot import constants


def add_blueprints(application):
    from albumlistbot.views.api import api_blueprint
    application.register_blueprint(api_blueprint)
    api_blueprint.config = application.config.copy()

    from albumlistbot.views.slack import slack_blueprint
    application.register_blueprint(slack_blueprint)
    slack_blueprint.config = application.config.copy()


def create_app():
    app = flask.Flask(__name__)
    if 'DYNO' in os.environ:
        app.logger.addHandler(logging.StreamHandler(sys.stdout))
        app.logger.setLevel(logging.INFO)
    app.config.from_object(os.environ['APP_SETTINGS'])
    add_blueprints(app)
    app.logger.info(f'[app]: created with {os.environ["APP_SETTINGS"]}')
    return app
