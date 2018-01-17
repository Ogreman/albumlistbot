import functools
import json
import re
from urllib.parse import urljoin, urlparse

import flask
import requests

from albumlistbot import constants
from albumlistbot.controllers import scrape_links_from_text, heroku, slack
from albumlistbot.models import DatabaseError, mapping


slack_blueprint = flask.Blueprint(name='slack',
                               import_name=__name__,
                               url_prefix='/slack')


def list_commands(*args, **kwargs):
    return '\n'.join(SLASH_COMMANDS.keys())


SLASH_COMMANDS = {
    'get': slack.get_albumlist,
    'set': slack.set_albumlist,
    'create': heroku.create_albumlist,
    'check': heroku.check_albumlist,
    'process_albums': slack.process_albums,
    'process_check': slack.process_check,
    'process_covers': slack.process_covers,
    'process_duplicates': slack.process_duplicates,
    'process_tags': slack.process_tags,
    'remove': slack.remove_albumlist,
    'heroku': heroku.auth_heroku,
    'help': list_commands,
}


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


@slack_blueprint.route('/albumlist', methods=['POST'])
@slack_check
def albumlist_commands():
    """
    Main entrypoint for the Slack slash commands

    e.g.: /albumlist get
          /albumlist set https://myalbumlist.herokuapp.com
          /albumlist create
          /albumlist check
          /albumlist remove
          /albumlist heroku
          /albumlist reauth (TODO)
          /albumlist test https://mynewlist.herokuapp.com (TODO)
          /albumlist process_albums
          /albumlist process_check
          /albumlist process_covers
          /albumlist process_duplicates
          /albumlist process_tags
    """
    form_data = flask.request.form
    team_id = form_data['team_id']
    user_id = form_data['user_id']
    text = form_data['text']
    try:
        app_url, slack_token, heroku_token = mapping.get_app_slack_heroku_for_team(team_id)
    except TypeError:
        return 'Team not authorised', 200
    if not slack_token:
        return 'Team not authorised', 200
    if not slack.is_slack_admin(slack_token, user_id):
        return 'Not authorised', 200
    command, *params = text.strip().split(' ')
    try:
        return SLASH_COMMANDS[command](
            team_id=team_id,
            app_url=app_url,
            slack_token=slack_token,
            heroku_token=heroku_token,
            form_data=form_data,
            params=params), 200
    except KeyError:
        return 'No such albumlist command', 200


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
        app_url = mapping.get_app_url_for_team(team_id)
    except DatabaseError as e:
        flask.current_app.logger.error(f'[db]: {e}')
        return 'Failed', 200
    return slack.route_commands_to_albumlist(team_id, app_url, uri, form_data), 200


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
                        heroku.set_config_variables_for_albumlist(app_url_or_name, heroku_token, config_dict, session=s)
                        flask.current_app.logger.info(f'[router]: updated albumlist with new access token')
            else:
                mapping.add_team_with_token(team_id, access_token)
                flask.current_app.logger.info(f'[router]: added {team_id} with {access_token}')
            return flask.redirect(slack.get_slack_team_url(access_token))
        except DatabaseError as e:
            flask.current_app.logger.error(f'[db]: {e}')
            return 'Failed to add team', 500
    return 'Failed', 500
