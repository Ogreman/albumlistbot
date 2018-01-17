# Albumlistbot

This is an app that manages albumlist applications. 

Click the button below to add the bot to your [Slack](https://slack.com) team and use it to `/register` your [Albumlist](https://github.com/Ogreman/albumlist) instance (using the full URL to the app, e.g.: `/set_albumlist https://myalbumlist.herokuapp.com`) or create a new Albumlist with the `/create_albumlist` command.

<a href="https://slack.com/oauth/authorize?client_id=10066701634.66761250224&scope=bot,commands,chat:write:bot,channels:history,links:read,users:read,team:read"><img alt="Add to Slack" height="40" width="139" src="https://platform.slack-edge.com/img/add_to_slack.png" srcset="https://platform.slack-edge.com/img/add_to_slack.png 1x, https://platform.slack-edge.com/img/add_to_slack@2x.png 2x" /></a>

## Deploy to Heroku

(Not necessary to use the functionality of the [Albumlist](https://github.com/Ogreman/albumlist) and bot!)

You can deploy this app yourself to [Heroku](https://heroku.com/) to play with - though I would suggest forking this repository first and tweaking the environment variables listed under "env" in the [app.json file](https://github.com/Ogreman/albumlistbot/blob/master/app.json).

[![Deploy](https://www.herokucdn.com/deploy/button.png)](https://heroku.com/deploy)

## Running services locally

Using [Docker Compose](https://docs.docker.com/compose/install/):

```
$ docker-compose up -d
$ docker-compose exec web python create_tables.py
```

Use [Pyenv](https://github.com/pyenv/pyenv) to manage installed Python versions:

```
$ curl -L https://raw.githubusercontent.com/pyenv/pyenv-installer/master/bin/pyenv-installer | bash
$ pyenv versions
* system
  2.7
  3.4.7
  3.5.4
  3.6.3
```

You can then set the default global Python version using:
```
$ pyenv global 3.6.3
$ pyenv versions
  system
  2.7
  3.4.7
  3.5.4
* 3.6.3 (set by /Users/User/.pyenv/version)

# if pip is missing:
$ easy_install pip
```

NB: install Python versions with:
```
$ pyenv install 3.6.3
```

Install dependencies to a new virtual environment using [Pipenv](https://docs.pipenv.org/):

```
$ pip install -U pipenv
$ pipenv install
```

NB: pipenv will try to use pyenv to install a missing version of Python specified in the Pipfile.

Run commands within the new virtual environment with:
```
pipenv run python create_tables.py
pipenv run python run.py
```
