from contextlib import closing
import json

import psycopg2

from albumlistbot.models import DatabaseError, get_connection


def create_mapping_table():
    sql = """
        CREATE TABLE mapping (
        team varchar UNIQUE,
        app varchar UNIQUE
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


def add_mapping(team, app_url):
    sql = """
        INSERT INTO mapping (team, app) VALUES (%s, %s);"""
    with closing(get_connection()) as conn:
        try:
            cur = conn.cursor()
            cur.execute(sql, (team, app_url))
            conn.commit()
        except psycopg2.IntegrityError:
            raise DatabaseError(f'mapping already exists for {team} -> {app_url}')
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
