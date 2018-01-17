import functools
import json
import re
from urllib.parse import urljoin, urlparse

import flask
import requests
from slacker import Slacker

from albumlistbot import constants
from albumlistbot.controllers import scrape_links_from_text, heroku
from albumlistbot.models import DatabaseError
from albumlistbot.models import mapping


slack_blueprint = flask.Blueprint(name='slack',
                               import_name=__name__,
                               url_prefix='/slack')


def slack_check(func):
    """
    Decorator for locking down Slack endpoints to registered apps only
    """
    @functools.wraps(func)
    def wraps(*args, **kwargs):
        if 'payload' in flask.request.form or flask.request.form.get('token', '') == slack_blueprint.config['APP_TOKEN'] or slack_blueprint.config['DEBUG']:
            return func(*args, **kwargs)
        flask.current_app.logger.error('[access]: failed slack-check test')
        flask.abort(403)
    return wraps


def get_slack_team_url(token):
    slack = Slacker(token)
    flask.current_app.logger.info(f'[router]: getting team info...')
    info = slack.team.info()
    return f"https://{info.body['team']['domain']}.slack.com"


def is_slack_admin(token, user_id):
    slack = Slacker(token)
    flask.current_app.logger.info(f'[router]: performing admin check...')
    info = slack.users.info(user_id)
    return info.body['user']['is_admin']



@slack_blueprint.route('/get_list', methods=['POST'])
@slack_check
def get_list():
    form_data = flask.request.form
    team_id = form_data['team_id']
    user_id = form_data['user_id']
    try:
        app_url, token = mapping.get_app_and_slack_token_for_team(team_id)
    except TypeError:
        return 'Team not authorised', 200
    if not token:
        return 'Team not authorised', 200
    if not is_slack_admin(token, user_id):
        return 'Not authorised', 200
    if not app_url:
        return '', 200
    return app_url, 200


@slack_blueprint.route('/create_list', methods=['POST'])
@slack_check
def create_list():
    form_data = flask.request.form
    team_id = form_data['team_id']
    user_id = form_data['user_id']
    try:
        app_url, slack_token, heroku_token = mapping.get_app_slack_heroku_for_team(team_id)
    except TypeError:
        return 'Team not authorised', 200
    if not slack_token:
        return 'Team not authorised', 200
    if not is_slack_admin(slack_token, user_id):
        return 'Not authorised', 200
    if not heroku_token:
        return 'Missing Heroku OAuth', 200
    if not app_url:
        app_name = heroku.create_new_albumlist(team_id, slack_token, heroku_token)
        if not app_name:
            return 'Failed', 200
        try:
            mapping.set_mapping_for_team(team_id, app_name)
        except DatabaseError as e:
            flask.current_app.logger.error(f'[db]: {e}')
            return 'Failed', 200
        return 'Creating new albumlist...', 200
    else:
        attachment = {
            'fallback': 'Replace existing list?',
            'title': 'Replace existing list?',
            'callback_id': f'create_list_{team_id}',
            'actions': [
                {
                    'name': 'yes',
                    'text': 'Yes',
                    'type': 'button',
                    'value': team_id,
                },
                {
                    'name': 'no',
                    'text': 'No',
                    'type': 'button',
                    'value': team_id,
                }
            ],
        }
        response = {
            'response_type': 'ephemeral',
            'text': f'An existing albumlist was found...',
            'attachments': [attachment],
        }
        return flask.jsonify(response), 200
    return '', 200


@slack_blueprint.route('/check', methods=['POST'])
@slack_check
def check_albumlist():
    form_data = flask.request.form
    team_id = form_data['team_id']
    try:
        app, heroku_token = mapping.get_app_and_heroku_token_for_team(team_id)
    except TypeError:
        return 'Team not authorised', 200
    except DatabaseError as e:
        flask.current_app.logger.error(f'[db]: {e}')
        return 'Failed', 200
    if not app:
        return 'No albumlist mapped to this team (admins: use /create_albumlist to get started)'
    if scrape_links_from_text(app):
        flask.current_app.logger.info(f'[router]: checking connection to {app} for {team_id}')
        try:
            response = requests.head(app, timeout=2.0)
        except requests.exceptions.Timeout:
            return 'The connection to the albumlist timed out', 200
        if response.ok:
            return 'OK', 200
        flask.current_app.logger.info(f'[router]: connection to {app} failed: {response.status_code}')
        return f'Failed ({response.status_code})'
    if not heroku_token:
        return 'Missing Heroku OAuth', 200
    if heroku.check_and_update(team_id, app, heroku_token):
        return 'OK', 200
    return 'Failed. Try running /check_albumlist again', 200


@slack_blueprint.route('/set_albumlist', methods=['POST'])
@slack_check
def set_mapping():
    form_data = flask.request.form
    team_id = form_data['team_id']
    user_id = form_data['user_id']
    token = mapping.get_slack_token_for_team(team_id)
    if not token:
        return 'Team not authorised', 200
    if not is_slack_admin(token, user_id):
        return 'Not authorised', 200
    try:
        app_url = scrape_links_from_text(form_data['text'])[0]
    except IndexError:
        return 'Provide an URL for the Albumlist', 200
    flask.current_app.logger.info(f'[router]: registering {team_id} with {app_url}')
    try:
        mapping.set_mapping_for_team(team_id, app_url)
    except DatabaseError as e:
        flask.current_app.logger.error(f'[db]: {e}')
        return 'Team not authed or already registered', 200
    return 'Registered your Slack team with the provided Albumlist', 200


@slack_blueprint.route('/remove_albumlist', methods=['POST'])
@slack_check
def remove_mapping():
    form_data = flask.request.form
    team_id = form_data['team_id']
    user_id = form_data['user_id']
    app_url, token = mapping.get_app_and_slack_token_for_team(team_id)
    if not token:
        return 'Team not authorised', 200
    if not is_slack_admin(token, user_id):
        return 'Not authorised', 200
    if app_url:
        attachment = {
            'fallback': 'Remove existing list?',
            'title': 'Remove existing list?',
            'callback_id': f'delete_list_{team_id}',
            'actions': [
                {
                    'name': 'yes',
                    'text': 'Yes',
                    'type': 'button',
                    'value': team_id,
                },
                {
                    'name': 'no',
                    'text': 'No',
                    'type': 'button',
                    'value': team_id,
                }
            ],
        }
        response = {
            'response_type': 'ephemeral',
            'text': 'Warning! Your albumlist will be removed...',
            'attachments': [attachment],
        }
        return flask.jsonify(response), 200
    try:
        mapping.delete_from_mapping(team_id)
    except DatabaseError as e:
        flask.current_app.logger.error(f'[db]: {e}')
        return '', 200
    return 'Unregistered the Albumlist for your Slack team (re-add albumlistbot to Slack to use again)', 200


@slack_blueprint.route('/route', methods=['POST'])
@slack_check
def route_to_app():
    form_data = flask.request.form.copy()
    uri = flask.request.args['uri']
    if 'payload' in form_data:
        json_data = json.loads(form_data['payload'])
        team_id = json_data['team']['id']
        if json_data['callback_id'] == f'create_list_{team_id}':
            if 'yes' in json_data['actions'][0]['name']:
                slack_token, heroku_token = mapping.get_tokens_for_team(team_id)
                if not slack_token:
                    return 'Team not authorised', 200
                if not heroku_token:
                    return 'Missing Heroku OAuth', 200
                app_name = heroku.create_new_albumlist(team_id, slack_token, heroku_token)
                if not app_name:
                    return 'Failed', 200
                try:
                    mapping.set_mapping_for_team(team_id, app_name)
                except DatabaseError as e:
                    flask.current_app.logger.error(f'[db]: {e}')
                    return 'Failed', 200
                return 'Creating new albumlist...', 200
            return 'OK', 200
        elif json_data['callback_id'] == f'delete_list_{team_id}':
            if 'yes' in json_data['actions'][0]['name']:
                try:
                    mapping.delete_from_mapping(team_id)
                    flask.current_app.logger.info(f'[router]: deleted mapping for {team_id}')
                except DatabaseError as e:
                    flask.current_app.logger.error(f'[db]: {e}')
                    return 'Failed', 200
                return 'Unregistered the Albumlist for your Slack team (re-add albumlistbot to Slack to use again)', 200
            return 'OK', 200
    else:
        team_id = form_data['team_id']
    try:
        app_url, token = mapping.get_app_and_slack_token_for_team(team_id)
        if not app_url:
            return 'Failed (use /set_albumlist [url] first to use Albumlist commands)', 200
        if not scrape_links_from_text(app_url):
            return 'Failed (try /check)', 200
    except DatabaseError as e:
        flask.current_app.logger.error(f'[db]: {e}')
        return 'Failed', 200
    full_url = f'{urljoin(app_url, "slack")}/{uri}'
    flask.current_app.logger.info(f'[router]: connecting {team_id} to {full_url}...')
    try:
        response = requests.post(full_url, data=form_data, timeout=2.0)
    except requests.exceptions.Timeout:
        return 'The connection to the albumlist timed out', 200
    if not response.ok:
        flask.current_app.logger.error(f'[router]: connection error for {team_id} to {full_url}: {response.status_code}')
        return 'Failed', 200
    try:
        return flask.jsonify(response.json()), 200
    except ValueError:
        return response.text, 200


@slack_blueprint.route('/route/events', methods=['POST'])
def route_events_to_app():
    if int(flask.request.headers.get('X-Slack-Retry-Num', 0)) > 1:
        return '', 200
    json_data = flask.request.json.copy()
    request_type = json_data['type']
    if request_type == 'url_verification':
        return flask.jsonify({'challenge': json_data['challenge']})
    if json_data['token'] != slack_blueprint.config['APP_TOKEN']:
        return '', 200
    team_id = json_data['team_id']
    try:
        app_url, token = mapping.get_app_and_slack_token_for_team(team_id)
        if not app_url or not scrape_links_from_text(app_url):
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


@slack_blueprint.route('/heroku/auth', methods=['POST'])
@slack_check
def auth_heroku():
    form_data = flask.request.form
    team_id = form_data['team_id']
    user_id = form_data['user_id']
    token = mapping.get_slack_token_for_team(team_id)
    if not token:
        return 'Team not authorised', 200
    if not is_slack_admin(token, user_id):
        return 'Not authorised', 200
    url = constants.HEROKU_AUTH_URL.format(
        client_id=slack_blueprint.config['HEROKU_CLIENT_ID'],
        csrf_token=slack_blueprint.config['CSRF_TOKEN'] + f':{team_id}')
    attachment = {
        "fallback": "Heroku",
        "title_link": url,
        "title": "Create OAuth token",
        "footer": "Albumlistbot",
    }
    response = {
        'response_type': 'ephemeral',
        'text': 'Click the link to allow Albumlistbot to manage your Heroku apps',
        'attachments': [attachment],
    }
    return flask.jsonify(response), 200


@slack_blueprint.route('/auth', methods=['GET'])
def auth():
    code = flask.request.args.get('code')
    client_id = slack_blueprint.config['SLACK_CLIENT_ID']
    client_secret = slack_blueprint.config['SLACK_CLIENT_SECRET']
    url = constants.SLACK_AUTH_URL.format(code=code, client_id=client_id, client_secret=client_secret)
    response = requests.get(url)
    response_json = response.json()
    flask.current_app.logger.info(f'[auth]: {response_json}')
    if response.ok and response_json.get('ok'):
        team_id = response_json['team_id']
        access_token = response_json['access_token']
        try:
            if mapping.team_exists(team_id):
                mapping.set_slack_token_for_team(team_id, access_token)
                flask.current_app.logger.info(f'[router]: set new token {access_token} for {team_id}')
                app_url_or_name, heroku_token = mapping.get_app_and_heroku_token_for_team(team_id)
                with requests.Session() as s:
                    if app_url_or_name and heroku.is_managed(app_url_or_name, heroku_token, session=s):
                        config_dict = {'SLACK_OAUTH_TOKEN': access_token}
                        set_config_variables_for_albumlist(app_url_or_name, heroku_token, config_dict, session=s)
                        flask.current_app.logger.info(f'[router]: updated albumlist with new access token')
                return flask.redirect(get_slack_team_url(access_token))
            else:
                mapping.add_team_with_token(team_id, access_token)
                flask.current_app.logger.info(f'[router]: added {team_id} with {access_token}')
                return flask.redirect(get_slack_team_url(access_token))
        except DatabaseError as e:
            flask.current_app.logger.error(f'[db]: {e}')
            return 'Failed to add team', 500
    return 'Failed', 500
