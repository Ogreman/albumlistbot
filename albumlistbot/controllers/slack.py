import functools
from urllib.parse import urljoin

import flask
import requests
from slacker import Slacker

from albumlistbot.controllers import scrape_links_from_text
from albumlistbot.models import mapping, DatabaseError


def route_commands_to_albumlist(team_id, app_url, uri, form_data, *args, **kwargs):
    if not app_url:
        return 'Failed (use `/albumlist set [url]` first to use Albumlist commands)'
    if not scrape_links_from_text(app_url):
        return 'Failed (try `/albumlist check`)'
    full_url = f'{urljoin(app_url, "slack")}/{uri}'
    flask.current_app.logger.info(f'[router]: connecting {team_id} to {full_url}...')
    try:
        response = requests.post(full_url, data=form_data, timeout=2.0)
    except requests.exceptions.Timeout:
        return 'The connection to the albumlist timed out'
    if not response.ok:
        flask.current_app.logger.error(f'[router]: connection error for {team_id} to {full_url}: {response.status_code}')
        return 'Failed'
    try:
        return flask.jsonify(response.json())
    except ValueError:
        return response.text


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


def get_albumlist(app_url, *args, **kwargs):
    return app_url


def set_albumlist(team_id, form_data, *args, **kwargs):
    try:
        app_url = scrape_links_from_text(form_data['text'])[0]
    except IndexError:
        return 'Provide an URL for the Albumlist'
    flask.current_app.logger.info(f'[router]: registering {team_id} with {app_url}')
    try:
        mapping.set_mapping_for_team(team_id, app_url)
    except DatabaseError as e:
        flask.current_app.logger.error(f'[db]: {e}')
        return 'Team not authed or already registered'
    return 'Registered your Slack team with the provided Albumlist'


def remove_albumlist(team_id, app_url, *args, **kwargs):
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
        return flask.jsonify(response)
    try:
        mapping.delete_from_mapping(team_id)
    except DatabaseError as e:
        flask.current_app.logger.error(f'[db]: {e}')
        return ''
    return 'Unregistered the Albumlist for your Slack team (admins: use `/albumlist slack` to authenticate again)'


def auth_slack(team_id, *args, **kwargs):
    flask.current_app.logger.info(f'[router]: creating URL to authenticate slack for {team_id}')
    url = flask.current_app.config['ADD_TO_SLACK_URL']
    attachment = {
        "fallback": "Slack",
        "title_link": url,
        "title": "Create OAuth token",
        "footer": "Albumlistbot",
    }
    response = {
        'response_type': 'ephemeral',
        'text': 'Click the link to authenticate Albumlistbot',
        'attachments': [attachment],
    }
    return flask.jsonify(response)


process_albums = functools.partial(route_commands_to_albumlist, uri='process')
process_check = functools.partial(route_commands_to_albumlist, uri='process/check')
process_covers = functools.partial(route_commands_to_albumlist, uri='process/covers')
process_duplicates = functools.partial(route_commands_to_albumlist, uri='process/duplicates')
process_tags = functools.partial(route_commands_to_albumlist, uri='process/tags')
clear_cache = functools.partial(route_commands_to_albumlist, uri='clear')
restore_from_url = functools.partial(route_commands_to_albumlist, uri='restore_from_url')
