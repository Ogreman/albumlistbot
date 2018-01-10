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


def slack_check(func):
    """
    Decorator for locking down slack endpoints to registered apps only
    """
    @functools.wraps(func)
    def wraps(*args, **kwargs):
        if flask.request.form.get('token', '') in slack_blueprint.config['APP_TOKENS'] or slack_blueprint.config['DEBUG']:
            return func(*args, **kwargs)
        print('[access]: failed slack-check test')
        flask.abort(403)
    return wraps


def scrape_links_from_text(text):
    return [url for url in re.findall(constants.URL_REGEX, text)]


@slack_blueprint.route('/register', methods=['POST'])
@slack_check
def register():
    form_data = flask.request.form
    team_id = form_data['team_id']
    app_url = scrape_links_from_text(form_data['text'])[0]
    mapping.add_mapping(team_id, app_url)
    return 'Registered your Slack team with your Albumlist', 200


@slack_blueprint.route('/delete', methods=['POST'])
@slack_check
def delete():
    form_data = flask.request.form
    team_id = form_data['team_id']
    mapping.delete_from_mapping(team_id)
    return 'Removed mapping for your Slack team', 200


@slack_blueprint.route('/route', methods=['POST'])
@slack_check
def route_to_app():
    form_data = flask.request.form
    uri = flask.request.args['uri']
    team_id = form_data['team_id']
    app_url = mapping.get_app_url_for_team(team_id)
    full_url = f'{urljoin(app_url, "slack")}/{uri}'
    response = requests.post(full_url, data=form_data)
    return flask.jsonify(response.json() or response.text), 200


@slack_blueprint.route('/route/events', methods=['POST'])
@slack_check
def route_events_to_app():
    json_data = flask.request.json
    request_type = json_data['type']
    if request_type == 'url_verification':
        return flask.jsonify({'challenge': json_data['challenge']})
    team_id = json_data['team_id']
    app_url = mapping.get_app_url_for_team(team_id)
    full_url = urljoin(app_url, 'slack/events')
    requests.post(full_url, json=json_data)
    return '', 200


@slack_blueprint.route('/auth', methods=['GET'])
@slack_check
def auth():
    code = flask.request.args.get('code')
    client_id = slack_blueprint.config['SLACK_CLIENT_ID']
    client_secret = slack_blueprint.config['SLACK_CLIENT_SECRET']
    url = constants.SLACK_AUTH_URL.format(code=code, client_id=client_id, client_secret=client_secret)
    response = requests.get(url)
    print(f'[auth]: {response.json()}')
    return response.content, 200
