import logging
import os
import sys

import flask

from albumlistbot import constants


def add_blueprints(application):
    from albumlistbot.views.api import api_blueprint
    application.register_blueprint(api_blueprint)
    api_blueprint.config = application.config.copy()

    from albumlistbot.views.heroku import heroku_blueprint
    application.register_blueprint(heroku_blueprint)
    heroku_blueprint.config = application.config.copy()

    from albumlistbot.views.slack import slack_blueprint
    application.register_blueprint(slack_blueprint)
    slack_blueprint.config = application.config.copy()


def create_app():
    app = flask.Flask(__name__)
    if 'DYNO' in os.environ:
        app.logger.addHandler(logging.StreamHandler(sys.stdout))
        app.logger.setLevel(logging.DEBUG)
    app.config.from_object(os.environ['APP_SETTINGS'])
    if app.config["DISABLE_DATABASE"]:
        app.logger.info(f'[app]: database disabled')
    add_blueprints(app)
    app.logger.debug(f'[app]: created with {os.environ["APP_SETTINGS"]}')
    return app
