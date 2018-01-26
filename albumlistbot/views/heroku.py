import flask
import requests

from albumlistbot import constants
from albumlistbot.controllers import heroku
from albumlistbot.models import DatabaseError, mapping


heroku_blueprint = flask.Blueprint(name='heroku',
                               import_name=__name__,
                               url_prefix='/heroku')



@heroku_blueprint.route('/oauth', methods=['GET'])
def oauth_redirect():
    client_secret = heroku_blueprint.config['HEROKU_CLIENT_SECRET']
    csrf = heroku_blueprint.config['CSRF_TOKEN']
    state = flask.request.args.get('state', '')
    code = flask.request.args.get('code')
    if not state.startswith(csrf):
        return 'Failed'
    team_id = state[len(csrf) + 1:]
    if not team_id:
        return 'Failed'
    payload = {
        'grant_type': 'authorization_code',
        'code': code,
        'client_secret': client_secret,
    }
    flask.current_app.logger.info(f'[heroku]: getting new token for {team_id}...')
    response = requests.post(constants.HEROKU_TOKEN_URL, data=payload)
    response_json = response.json()
    if not response.ok:
        flask.current_app.logger.error(f'[heroku]: failed to get token for {team_id}: {response.status_code}')
        flask.current_app.logger.error(f'[heroku]: {response_json}')
        return 'Failed'
    access_token = response_json['access_token']
    refresh_token = response_json['refresh_token']
    flask.current_app.logger.info(f'[heroku]: {team_id}: {access_token}')
    try:
        mapping.set_heroku_and_refresh_token_for_team(team_id, access_token, refresh_token)
    except DatabaseError as e:
        flask.current_app.logger.error(f'[db]: {e}')
        return 'Failed'
    flask.current_app.logger.info(f'[heroku]: added heroku token to db for {team_id}')
    return 'OK'
