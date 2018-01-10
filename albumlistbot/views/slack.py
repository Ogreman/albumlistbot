import functools
import re
from urllib.parse import urljoin

import flask
import requests

from albumlistbot import constants
from albumlistbot.models import DatabaseError
from albumlistbot.models import mapping


slack_blueprint = flask.Blueprint(name='slack',
                               import_name=__name__,
                               url_prefix='/slack')


def scrape_links_from_text(text):
    return [url for url in re.findall(constants.URL_REGEX, text)]


@slack_blueprint.route('/register', methods=['POST'])
def register():
    form_data = flask.request.form
    team_id = form_data['team_id']
    app_url = scrape_links_from_text(form_data['text'])[0]
    mapping.add_mapping(team_id, app_url)
    return 'Registered your Slack team with your Albumlist', 200


@slack_blueprint.route('/delete', methods=['POST'])
def delete():
    form_data = flask.request.form
    team_id = form_data['team_id']
    mapping.delete_from_mapping(team_id)
    return 'Removed mapping for your Slack team', 200


@slack_blueprint.route('/route', methods=['POST'])
def route_to_app():
    form_data = flask.request.form
    uri = flask.request.args['uri']
    team_id = form_data['team_id']
    app_url = mapping.get_app_url_for_team(team_id)
    full_url = urljoin(app_url, uri)
    return requests.post(full_url, data=form_data).text, 200
