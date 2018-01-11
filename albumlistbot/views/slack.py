import functools
import json
import logging
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
        if 'payload' in flask.request.form or flask.request.form.get('token', '') in slack_blueprint.config['APP_TOKENS'] or slack_blueprint.config['DEBUG']:
            return func(*args, **kwargs)
        flask.current_app.logger.error('[access]: failed slack-check test')
        flask.abort(403)
    return wraps


def scrape_links_from_text(text):
    return [url for url in re.findall(constants.URL_REGEX, text)]


@slack_blueprint.route('/register', methods=['POST'])
@slack_check
def register():
    form_data = flask.request.form
    team_id = form_data['team_id']
    if mapping.get_app_url_for_team(team_id):
        return 'Team already registered (use /unregister first to change)'
    try:
        app_url = scrape_links_from_text(form_data['text'])[0]
    except IndexError:
        return 'Provide an URL for the Albumlist', 200
    flask.current_app.logger.info(f'[router]: registering {team_id} with {app_url}')
    admin_url = urljoin(app_url, 'slack/admin/check')
    flask.current_app.logger.info(f'[router]: performing admin check at {admin_url}...')
    response = requests.post(admin_url, data=form_data)
    if not response.ok:
        flask.current_app.logger.error(f'[router]: connection error for {team_id} to {admin_url}: {response.status_code}')
        if response.status_code == 403:
            return 'Not authorised', 200
        return 'Failed (check the Albumlist is running and up to date)', 200
    try:
        mapping.add_mapping(team_id, app_url)
    except DatabaseError as e:
        flask.current_app.logger.error(f'[db]: {e}')
        return 'Team already registered (use /unregister first to change)', 200
    return 'Registered your Slack team with the provided Albumlist', 200


@slack_blueprint.route('/unregister', methods=['POST'])
@slack_check
def unregister():
    form_data = flask.request.form
    team_id = form_data['team_id']
    app_url = mapping.get_app_url_for_team(team_id)
    admin_url = urljoin(app_url, 'slack/admin/check')
    flask.current_app.logger.info(f'[router]: performing admin check at {admin_url}...')
    response = requests.post(admin_url, data=form_data)
    if not response.ok:
        flask.current_app.logger.error(f'[router]: connection error for {team_id} to {admin_url}: {response.status_code}')
        if response.status_code == 403:
            return 'Not authorised', 200
        return 'Failed (check the Albumlist is running and up to date)', 200
    try:
        mapping.delete_from_mapping(team_id)
    except DatabaseError as e:
        flask.current_app.logger.error(f'[db]: {e}')
        return '', 200
    return 'Unregistered the Albumlist for your Slack team', 200


@slack_blueprint.route('/route', methods=['POST'])
@slack_check
def route_to_app():
    form_data = flask.request.form
    uri = flask.request.args['uri']
    if 'payload' in form_data:
        json_data = json.loads(form_data['payload'])
        team_id = json_data['team']['id']
    else:
        team_id = form_data['team_id']
    try:
        app_url = mapping.get_app_url_for_team(team_id)
        if not app_url:
            return 'Failed (use /register [url] first to use Albumlist commands)', 200
    except DatabaseError as e:
        flask.current_app.logger.error(f'[db]: {e}')
        return 'Failed', 200
    full_url = f'{urljoin(app_url, "slack")}/{uri}'
    flask.current_app.logger.info(f'[router]: connecting {team_id} to {full_url}...')
    response = requests.post(full_url, data=form_data)
    if not response.ok:
        flask.current_app.logger.error(f'[router]: connection error for {team_id} to {full_url}: {response.status_code}')
        return 'Failed', 200
    try:
        return flask.jsonify(response.json()), 200
    except ValueError:
        return response.text, 200


@slack_blueprint.route('/route/events', methods=['POST'])
@slack_check
def route_events_to_app():
    json_data = flask.request.json
    request_type = json_data['type']
    if request_type == 'url_verification':
        return flask.jsonify({'challenge': json_data['challenge']})
    team_id = json_data['team_id']
    try:
        app_url = mapping.get_app_url_for_team(team_id)
        if not app_url:
            return '', 200
    except DatabaseError as e:
        flask.current_app.logger.error(f'[db]: {e}')
        return '', 200
    full_url = urljoin(app_url, 'slack/events')
    flask.current_app.logger.info(f'[router]: connecting {team_id} to {full_url}...')
    response = requests.post(full_url, json=json_data)
    if not response.ok:
        flask.current_app.logger.error(f'[router]: connection error to {full_url}: {response.status_code}')
    return '', 200


@slack_blueprint.route('/auth', methods=['GET'])
def auth():
    code = flask.request.args.get('code')
    client_id = slack_blueprint.config['SLACK_CLIENT_ID']
    client_secret = slack_blueprint.config['SLACK_CLIENT_SECRET']
    url = constants.SLACK_AUTH_URL.format(code=code, client_id=client_id, client_secret=client_secret)
    response = requests.get(url)
    flask.current_app.logger.info(f'[auth]: {response.json()}')
    return response.content, 200
