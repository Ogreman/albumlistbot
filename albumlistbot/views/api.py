import flask
import logging

from albumlistbot.controllers import heroku
from albumlistbot.models import DatabaseError, mapping


api_blueprint = flask.Blueprint(name='api',
                                import_name=__name__,
                                url_prefix='/api')


@api_blueprint.after_request
def after_request(response):
    if hasattr(response, 'headers'):
        response.headers['Access-Control-Allow-Origin'] = '*'
    return response


@api_blueprint.route('/mappings', methods=['GET'])
def api_mappings():
    try:
        return flask.jsonify(mapping.get_mappings()), 200
    except DatabaseError as e:
        flask.current_app.logger.error('[db]: failed to get mappings')
        flask.current_app.logger.error(f'[db]: {e}')
        return flask.jsonify({'text': 'failed'}), 500


@api_blueprint.route('/mapping/<team_id>', methods=['GET'])
def api_map_team_id_to_app_url(team_id):
    try:
        return flask.jsonify(mapping.get_app_url_for_team(team_id)), 200
    except DatabaseError as e:
        flask.current_app.logger.error('[db]: failed to get mappings')
        flask.current_app.logger.error(f'[db]: {e}')
        return flask.jsonify({'text': 'failed'}), 500


@api_blueprint.route('', methods=['GET'])
def all_endpoints():
    rules = [
        (list(rule.methods), rule.rule) 
        for rule in flask.current_app.url_map.iter_rules() 
        if rule.endpoint.startswith('api')
    ]
    return flask.jsonify({'api': rules}), 200


@api_blueprint.route('/ping', methods=['GET'])
def albumlist_wake():
    slack_token = flask.request.args['token']
    if flask.current_app.config["DISABLE_DATABASE"]:
        team_id, app_url, heroku_token = (mapping.get_team_app_by_slack(slack_token), None)
    else:
        team_id, app_url, heroku_token = mapping.get_team_app_heroku_by_slack(slack_token)
    heroku.check_albumlist(team_id, app_url, heroku_token)
    return '', 200
