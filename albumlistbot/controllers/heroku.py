from urllib.parse import urljoin, urlparse

import flask
import requests

from albumlistbot import constants
from albumlistbot.controllers import scrape_links_from_text
from albumlistbot.models import DatabaseError, mapping


def set_heroku_headers(heroku_token):
    headers = constants.HEROKU_HEADERS.copy()
    headers['Authorization'] = headers['Authorization'].format(heroku_token=heroku_token)
    return headers


def is_managed(team_id, app_url_or_name, heroku_token, session=requests):
    if not heroku_token or not app_url_or_name:
        return
    app_name = urlparse(app_url_or_name).hostname.split('.')[0] if scrape_links_from_text(app_url_or_name) else app_url_or_name
    flask.current_app.logger.info(f'[heroku]: checking if {app_name} is managed...')
    url = f"{urljoin(constants.HEROKU_API_URL, 'apps')}/{app_name}"
    headers = set_heroku_headers(heroku_token)
    response = session.get(url, headers=headers, timeout=1.5)
    flask.current_app.logger.debug(f'[heroku][{response.status_code}]: {response.json()}')
    if response.status_code == 401:
        flask.current_app.logger.info(f'[heroku]: heroku auth failed...')
        return refresh_heroku(team_id, session)
    return heroku_token


def create_albumlist(team_id, app_url, slack_token, heroku_token, *args, **kwargs):
    if not heroku_token:
        return 'Missing Heroku OAuth'
    if not app_url:
        with requests.Session() as s:
            app_name = create_new_albumlist(team_id, slack_token, heroku_token, s)
        if not app_name:
            return 'Failed'
        try:
            mapping.set_mapping_for_team(team_id, app_name)
        except DatabaseError as e:
            flask.current_app.logger.error(f'[db]: {e}')
            return 'Failed'
        return 'Creating new albumlist...'
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
    return flask.jsonify(response)


def create_new_albumlist(team_id, slack_token, heroku_token, session=requests):
    if not heroku_token:
        return
    flask.current_app.logger.info(f'[heroku]: creating a new albumlist for {team_id}...')
    url = urljoin(constants.HEROKU_API_URL, 'app-setups')
    headers = set_heroku_headers(heroku_token)
    source = f'{flask.current_app.config["ALBUMLIST_GIT_URL"]}/tarball/master/'
    app_token = flask.current_app.config['APP_TOKEN']
    bot_url = flask.current_app.config['ALBUMLISTBOT_URL']
    payload = {
        'app': {
            'region': 'eu',
            'stack': 'container',
        },
        'source_blob': {
            'url': source,
        },
        'overrides': {
            'env': {
                'APP_TOKEN_BOT': app_token,
                'SLACK_OAUTH_TOKEN': slack_token,
                'ALBUMLISTBOT_URL': bot_url,
            },
        },
    }
    response = session.post(url, headers=headers, json=payload)
    response_json = response.json()
    flask.current_app.logger.debug(f'[heroku]: {response_json}')
    if response.status_code == 401:
        heroku_token = refresh_heroku(team_id, session)
        if not heroku_token:
            return
        headers = set_heroku_headers(heroku_token)
        response = session.post(url, headers=headers, json=payload)
        response_json = response.json()
        flask.current_app.logger.debug(f'[heroku]: {response_json}')
    if response.ok:
        app_name = response_json['app']['name']
        flask.current_app.logger.info(f'[heroku]: created {app_name}')
        return app_name
    flask.current_app.logger.error(f'[heroku]: failed to create new albumlist for {team_id}: {response.status_code}')


def set_config_variables_for_albumlist(app_url_or_name, heroku_token, config_dict, session=requests):
    if scrape_links_from_text(app_url_or_name):
        app_url_or_name = urlparse(app_url_or_name).hostname.split('.')[0]
    flask.current_app.logger.info(f'[heroku]: updating config variables for {app_url_or_name}...')
    url = f"{urljoin(constants.HEROKU_API_URL, 'apps')}/{app_url_or_name}/config-vars"
    headers = set_heroku_headers(heroku_token)
    response = session.patch(url, headers=headers, json=config_dict)
    if response.ok:
        flask.current_app.logger.info(f'[heroku]: updated config variables {app_url_or_name}: {response.json()}')
        return
    flask.current_app.logger.error(f'[heroku]: failed to update config variables for {app_url_or_name}: {response.status_code}')


def get_config_variable_for_albumlist(app_url_or_name, heroku_token, config_name, session=requests):
    if scrape_links_from_text(app_url_or_name):
        app_url_or_name = urlparse(app_url_or_name).hostname.split('.')[0]
    flask.current_app.logger.info(f'[heroku]: retrieving config variables for {app_url_or_name}...')
    url = f"{urljoin(constants.HEROKU_API_URL, 'apps')}/{app_url_or_name}/config-vars"
    headers = set_heroku_headers(heroku_token)
    response = session.get(url, headers=headers)
    if response.ok:
        flask.current_app.logger.info(f'[heroku]: retrieved config variables {app_url_or_name}: {response.json()}')
        return response.json()[config_name]
    flask.current_app.logger.error(f'[heroku]: failed to retrieve config variables for {app_url_or_name}: {response.status_code}')


def albumlist_name(team_id, app_url, form_data, heroku_token, *args, **kwargs):
    name = form_data['text'].strip()
    with requests.Session() as s:
        heroku_token = is_managed(team_id, app_url, heroku_token, session=s)
        if heroku_token:
            if name:
                set_config_variables_for_albumlist(app_url, heroku_token, {'LIST_NAME': name}, session=s)
                return f':white_check_mark: {name}'
            else:
                return get_config_variable_for_albumlist(app_url, heroku_token, 'LIST_NAME', session=s)
    return 'Failed'


def check_and_update(team_id, app_name, heroku_token):
    try:
        with requests.Session() as s:
            heroku_token = is_managed(team_id, app_name, heroku_token, session=s)
            if not heroku_token:
                return False
            url = urljoin(constants.HEROKU_API_URL, f'apps/{app_name}/dynos')
            headers = set_heroku_headers(heroku_token)
            flask.current_app.logger.info(f'[heroku]: checking status of {app_name} dynos for {team_id}')
            response = s.get(url, headers=headers, timeout=1.5)
    except requests.exceptions.Timeout:
        flask.current_app.logger.error(f'[heroku]: API timed out')
        return False
    if not response.ok:
        return False
    flask.current_app.logger.info(f'[heroku]: app {app_name} is deployed')
    dynos = response.json()
    flask.current_app.logger.debug(f'[heroku]: {dynos}')
    if dynos and all(dyno['state'] == 'up' for dyno in dynos):
        app_url = f'https://{app_name}.herokuapp.com'
        flask.current_app.logger.info(f'[heroku]: registering {team_id} with {app_url}')
        try:
            mapping.set_mapping_for_team(team_id, app_url)
            flask.current_app.logger.info(f'[heroku]: {app_url} ready')
        except DatabaseError as e:
            flask.current_app.logger.error(f'[db]: {e}')
            return False
        else:
            return True
    return False


def check_albumlist(team_id, app_url, heroku_token, *args, **kwargs):
    if not app_url:
        return 'No albumlist mapped to this team (admins: use `/albumlist create` to get started)'
    if scrape_links_from_text(app_url):
        flask.current_app.logger.info(f'[router]: checking connection to {app_url} for {team_id}')
        try:
            response = requests.head(app_url, timeout=2.0)
        except requests.exceptions.Timeout:
            return 'The connection to the albumlist timed out'
        if response.ok:
            return 'OK'
        flask.current_app.logger.info(f'[router]: connection to {app_url} failed: {response.status_code}')
        return f'Failed ({response.status_code})'
    if not heroku_token:
        return 'Missing Heroku OAuth (admins: use `/albumlist heroku`)'
    if check_and_update(team_id, app_url, heroku_token):
        return 'OK'
    return 'Failed. (admins: try running `/albumlist check` again)'


def auth_heroku(team_id, *args, **kwargs):
    url = constants.HEROKU_AUTH_URL.format(
        client_id=flask.current_app.config['HEROKU_CLIENT_ID'],
        csrf_token=flask.current_app.config['CSRF_TOKEN'] + f':{team_id}')
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
    return flask.jsonify(response)


def refresh_heroku(team_id, session=requests):
    try:
        refresh_token = mapping.get_heroku_refresh_token_for_team(team_id)
    except DatabaseError as e:
        flask.current_app.logger.error(f'[db]: {e}')
        return
    if not refresh_token:
        flask.current_app.logger.error(f'[heroku]: refresh token missing for {team_id}')
        return
    payload = {
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
        'client_secret': flask.current_app.config['HEROKU_CLIENT_SECRET'],
    }
    flask.current_app.logger.info(f'[heroku]: refreshing heroku for {team_id}...')
    headers = {'Accept': 'application/vnd.heroku+json; version=3'}
    response = session.post(constants.HEROKU_TOKEN_URL, data=payload, headers=headers)
    response_json = response.json()
    if not response.ok:
        flask.current_app.logger.error(f'[heroku]: failed to get refresh token for {team_id}: {response.status_code}')
        flask.current_app.logger.error(f'[heroku]: {response_json}')
        return
    access_token = response_json['access_token']
    try:
        mapping.set_heroku_token_for_team(team_id, access_token)
    except DatabaseError as e:
        flask.current_app.logger.error(f'[db]: {e}')
        return
    flask.current_app.logger.info(f'[heroku]: added heroku token to db for {team_id}')
    return access_token


def scale_workers(team_id, app_url, form_data, heroku_token, *args, **kwargs):
    quantity = form_data['text'].strip()
    with requests.Session() as s:
        heroku_token = is_managed(team_id, app_url, heroku_token, session=s)
        if heroku_token:
            return scale_formation(app_url, heroku_token, quantity=quantity, session=s)
    return 'Failed'


def scale_formation(app_url_or_name, heroku_token, quantity=None, session=requests):
    if scrape_links_from_text(app_url_or_name):
        app_url_or_name = urlparse(app_url_or_name).hostname.split('.')[0]
    url = f"{urljoin(constants.HEROKU_API_URL, 'apps')}/{app_url_or_name}/formation"
    headers = set_heroku_headers(heroku_token)
    try:
        quantity = int(quantity)
        flask.current_app.logger.info(f'[heroku]: scaling dyno formation to {quantity} for {app_url_or_name}...')
        payload = {"updates": [
            {
                "quantity": 1,
                "size": "standard-1X" if quantity > 1 else "hobby",
                "type": "web"
            },
            {
                "quantity": quantity,
                "size": "standard-1X" if quantity > 1 else "hobby",
                "type": "worker"
            },
        ]}
        response = session.patch(url, headers=headers, json=payload)
    except ValueError:
        response = session.get(url, headers=headers)
    if response.ok:
        response_json = response.json()
        flask.current_app.logger.debug(f'[heroku]: current scale for {app_url_or_name}: {response_json}')
        return "\n".join([f"{dyno['quantity']} x {dyno['type']} ({dyno['size']})" for dyno in response_json])
    flask.current_app.logger.error(f'[heroku]: failed to scale formation for {app_url_or_name}: {response.status_code}')
    flask.current_app.logger.debug(f'[heroku]: {response.text}')
    return f':red_circle: failed to scale'


"""
TODO:
-> process check
<- send command
<- scale formation
-> process complete
<- scale formation
"""
