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


def is_managed(app_url_or_name, heroku_token, session=requests):
    if not heroku_token:
        return False
    if scrape_links_from_text(app_url_or_name):
        app_url_or_name = urlparse(app_url_or_name).hostname.split('.')[0]
    flask.current_app.logger.info(f'[heroku]: checking if {app_url_or_name} is managed...')
    url = f"{urljoin(constants.HEROKU_API_URL, 'apps')}/{app_url_or_name}"
    headers = set_heroku_headers(heroku_token)
    response = session.get(url, headers=headers, timeout=1.5)
    flask.current_app.logger.debug(f'[heroku]: {response.json()}')
    return response.ok


def create_new_albumlist(team_id, slack_token, heroku_token, session=requests):
    if not heroku_token:
        return
    flask.current_app.logger.info(f'[heroku]: creating a new albumlist for {team_id}...')
    url = urljoin(constants.HEROKU_API_URL, 'app-setups')
    headers = set_heroku_headers(heroku_token)
    source = f'{flask.current_app.config["ALBUMLIST_GIT_URL"]}/tarball/master/'
    app_token = flask.current_app.config['APP_TOKEN']
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
            },
        },
    }
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


def check_and_update(team_id, app_name, heroku_token):
    try:
        with requests.Session() as s:
            if not is_managed(app_name, heroku_token, session=s):
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
        except DatabaseError as e:
            flask.current_app.logger.error(f'[db]: {e}')
            return False
        else:
            return True
    return False