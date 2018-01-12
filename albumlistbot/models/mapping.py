from contextlib import closing
import json

import psycopg2

from albumlistbot.models import DatabaseError, get_connection


def create_mapping_table():
    sql = """
        CREATE TABLE mapping (
        team varchar UNIQUE,
        app varchar DEFAULT '',
        token varchar DEFAULT ''
        );"""
    with closing(get_connection()) as conn:
        try:
            cur = conn.cursor()
            cur.execute(sql)
            conn.commit()
        except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
            raise DatabaseError(e)


def get_mappings():
    sql = """
        SELECT team, app FROM mapping;
    """
    with closing(get_connection()) as conn:
        try:
            cur = conn.cursor()
            cur.execute(sql)
            return cur.fetchall()
        except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
            raise DatabaseError(e)


def team_exists(team):
    sql = """
        SELECT *
        FROM mapping
        WHERE team = %s;
    """
    with closing(get_connection()) as conn:
        try:
            cur = conn.cursor()
            cur.execute(sql, (team,))
            cur.fetchone()[0]
            return True
        except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
            raise DatabaseError(e)
        except (IndexError, TypeError):
            return False


def get_app_url_for_team(team):
    sql = """
        SELECT app
        FROM mapping
        WHERE team = %s;
    """
    with closing(get_connection()) as conn:
        try:
            cur = conn.cursor()
            cur.execute(sql, (team,))
            return cur.fetchone()[0]
        except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
            raise DatabaseError(e)
        except (IndexError, TypeError):
            return


def get_token_for_team(team):
    sql = """
        SELECT token
        FROM mapping
        WHERE team = %s;
    """
    with closing(get_connection()) as conn:
        try:
            cur = conn.cursor()
            cur.execute(sql, (team,))
            return cur.fetchone()[0]
        except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
            raise DatabaseError(e)
        except (IndexError, TypeError):
            return


def get_app_and_token_for_team(team):
    sql = """
        SELECT app, token
        FROM mapping
        WHERE team = %s;
    """
    with closing(get_connection()) as conn:
        try:
            cur = conn.cursor()
            cur.execute(sql, (team,))
            return cur.fetchone()
        except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
            raise DatabaseError(e)


def add_team(team, token):
    sql = """
        INSERT INTO mapping (team, token) VALUES (%s, %s);"""
    with closing(get_connection()) as conn:
        try:
            cur = conn.cursor()
            cur.execute(sql, (team, token))
            conn.commit()
        except psycopg2.IntegrityError:
            raise DatabaseError(f'mapping already exists for {team}')
        except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
            raise DatabaseError(e)


def set_mapping_for_team(team, app_url):
    sql = """
        UPDATE mapping
        SET app = %s
        WHERE team = %s;
        """
    with closing(get_connection()) as conn:
        try:
            cur = conn.cursor()
            cur.execute(sql, (app_url, team))
            conn.commit()
        except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
            raise DatabaseError(e)


def set_token_for_team(team, token):
    sql = """
        UPDATE mapping
        SET token = %s
        WHERE team = %s;
        """
    with closing(get_connection()) as conn:
        try:
            cur = conn.cursor()
            cur.execute(sql, (token, team))
            conn.commit()
        except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
            raise DatabaseError(e)


def _reset_mapping():
    with closing(get_connection()) as conn:
        try:
            cur = conn.cursor()
            cur.execute('DELETE FROM mapping')
            conn.commit()
        except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
            raise DatabaseError(e)


def delete_from_mapping(team):
    with closing(get_connection()) as conn:
        try:
            cur = conn.cursor()
            cur.execute('DELETE FROM mapping where team = %s;', (team,))
            conn.commit()
        except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
            raise DatabaseError(e)
