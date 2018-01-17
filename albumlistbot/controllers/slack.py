import flask
from slacker import Slacker

from albumlistbot.controllers import scrape_links_from_text
from albumlistbot.models import mapping, DatabaseError


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


def set_albumlist(team_id, params, *args, **kwargs):
    try:
        app_url = scrape_links_from_text(params[0])[0]
    except IndexError:
        return 'Provide an URL for the Albumlist', 200
    flask.current_app.logger.info(f'[router]: registering {team_id} with {app_url}')
    try:
        mapping.set_mapping_for_team(team_id, app_url)
    except DatabaseError as e:
        flask.current_app.logger.error(f'[db]: {e}')
        return 'Team not authed or already registered', 200
    return 'Registered your Slack team with the provided Albumlist', 200


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
    return 'Unregistered the Albumlist for your Slack team (re-add albumlistbot to Slack to use again)'
