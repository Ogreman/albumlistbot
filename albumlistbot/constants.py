URL_REGEX = 'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
HASHTAG_REGEX = '#(?:[a-zA-Z]|[0-9]|[-_.+])+'
SLACK_CHANNEL_REGEX = '<#(C[0-9A-Z]+)\|([a-z]+)>'
SLACK_AUTH_URL = 'https://slack.com/api/oauth.access?client_id={client_id}&client_secret={client_secret}&code={code}'
HEROKU_AUTH_URL = 'https://id.heroku.com/oauth/authorize?client_id={client_id}&response_type=code&scope=read-protected%20write-protected&state={csrf_token}'
HEROKU_TOKEN_URL = 'https://id.heroku.com/oauth/token'
HEROKU_API_URL = 'https://api.heroku.com'
HEROKU_HEADERS = {
    'Accept': 'application/vnd.heroku+json; version=3',
    'Authorization': 'Bearer {heroku_token}'
}