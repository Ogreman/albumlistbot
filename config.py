import os
import random
import string

random = random.SystemRandom()


class Config(object):
    DEBUG = False
    TESTING = False
    CSRF_ENABLED = True
    SECRET_KEY = os.environ.get('SECRET_KEY', 'change-me')
    HEROKU_CLIENT_ID = os.environ.get('HEROKU_CLIENT_ID')
    HEROKU_CLIENT_SECRET = os.environ.get('HEROKU_CLIENT_SECRET')
    ALBUMLIST_GIT_URL = os.environ.get('ALBUMLIST_GIT_URL')
    SLACK_CLIENT_ID = os.environ.get('SLACK_CLIENT_ID')
    SLACK_CLIENT_SECRET = os.environ.get('SLACK_CLIENT_SECRET')
    APP_TOKEN = os.environ.get('APP_TOKEN_SELF')
    CSRF_TOKEN = ''.join(random.choice(string.ascii_letters) for _ in range(25))
    ALBUMLISTBOT_URL = os.environ.get('ALBUMLISTBOT_URL')


class ProductionConfig(Config):
    DEBUG = False


class StagingConfig(Config):
    DEVELOPMENT = True
    DEBUG = False


class DevelopmentConfig(Config):
    DEVELOPMENT = True
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
