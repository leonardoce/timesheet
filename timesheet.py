#!/usr/bin/env python3

import configparser
import datetime
import requests
import sqlite3
import argparse

from re import sub
from requests.auth import HTTPBasicAuth


def get_clockwork_endpoint(config):
    return config['clockwork']['endpoint']


def get_clockwork_token(config):
    return config['clockwork']['token']


def get_jira_account_id(config):
    return config['jira']['account_id']


def get_jira_token(config):
    return config['jira']['token']


def get_jira_account_name(config):
    return config['jira']['account_name']


def get_jira_endpoint(config):
    return config['jira']['endpoint']


def get_sqlite_db_name(config):
    return config['db']['name']


def get_clockwork_records(config, start, end):
    """
    This function will invoke the Clockwork API to get the
    time entries between `start` and `end` and synchronize
    the time entries with the database
    """
    start_str = start.strftime("%Y-%m-%d")
    end_str = end.strftime("%Y-%m-%d")

    response = requests.get(get_clockwork_endpoint(config), params={
        "starting_at": start_str,
        "ending_at": end_str,
        "account_id": get_jira_account_id(config),
    }, headers={
        "Authorization": f"Token {get_clockwork_token(config)}"
    })
    response.raise_for_status()
    return response.json()


def jira_issue_info(config, issue_id):
    """
    Given a Jira ID, this function will get the issue info
    """
    response = requests.get(get_jira_endpoint(config).format(issue_id),
        auth=HTTPBasicAuth(get_jira_account_name(config), get_jira_token(config)))
    response.raise_for_status()
    return {
        "key": response.json()['key'],
        "summary": response.json()['fields']['summary'],
        "project": response.json()['key'][:3],
    }


def open_connection(config):
    """
    Open a connection to the database and return a cursor
    """
    return sqlite3.connect(get_sqlite_db_name(config))


def sync(config, horizon):
    """
    Synchronize the data from Jira to the local database
    """
    issue_map = dict()

    # Open db
    db = open_connection(config)
    cur = db.cursor()

    # Get clockwork records
    start = datetime.date.today() - datetime.timedelta(days=horizon)
    end = datetime.date.today()
    entries = get_clockwork_records(config, start, end)

    # Insert data into timesheet
    for entry in entries:
        id = entry['id']
        minutes = entry['timeSpentSeconds'] / 60
        day = datetime.datetime.strptime(entry['started'][:10], '%Y-%m-%d').strftime("%Y-%m-%d")
        issue_id = entry['issue']['id']
        issue_info = issue_map.get(issue_id)
        if not issue_info:
            issue_info = jira_issue_info(config, issue_id)
            issue_map[issue_id] = issue_info

        # Insert into the database
        cur.execute("UPDATE timesheet SET ticket=?, description = ?, minutes=?, project=?, day=? WHERE entry_id=?",
            (issue_info['key'], issue_info['summary'], minutes, issue_info['project'], day, id))
        if cur.rowcount == 0:
            db.execute("INSERT INTO timesheet (ticket, description, minutes, day, entry_id, project) VALUES (?,?,?,?,?,?)",
                (issue_info['key'], issue_info['summary'], minutes, day, id, issue_info['project']))
        
    db.commit()
    db.close()


def report(config, horizon):
    """
    Report how much time I spent working on each day, and then per project
    """

    start_time = datetime.datetime.today() - datetime.timedelta(days=horizon)

    db = open_connection(config)
    cur = db.cursor()

    cur.execute("SELECT project, sum(minutes)/60.0 "
        "FROM timesheet WHERE day >= ? GROUP BY 1",
        (start_time.strftime("%Y-%m-%d"),))
    data = cur.fetchall()

    for row in data:
        print(f"{row[0]}: {row[1]} hours")

    print()

    cur.execute(
        "SELECT day, SUM(minutes) FROM timesheet WHERE day >= ? GROUP BY day ORDER BY 1",
        (start_time.strftime("%Y-%m-%d"),))
    data = cur.fetchall()

    for row in data:
        print(f"{row[0]}: Total {row[1]/60.0} hours")

    cur.close()
    db.close()


def latest(config, horizon):
    """
    Report my latest time entries
    """

    db = open_connection(config)
    cur = db.cursor()

    cur.execute(
        "SELECT day, ticket, description, minutes, project FROM timesheet WHERE day >= ? ORDER BY 1",
        ((datetime.datetime.today() - datetime.timedelta(days=horizon)).strftime("%Y-%m-%d"),))
    data = cur.fetchall()

    for row in data:
        print(f"{row[0]}: {row[4]} ({row[1] or 'no ticket'}) {row[2]} [{row[3]/60} hours]")

    cur.close()
    db.close()

    print()
    report(config, horizon)


def create(config, project, minutes, description, ticket, day):
    """
    Create an entry in the journal
    :param config: the configuration
    :param project: the code of the project
    :param minutes: how many minutes to put
    :param description: the description of this activity
    :param ticket: the ticket number
    """

    db = open_connection(config)
    cur = db.cursor()

    cur.execute(
        "INSERT INTO timesheet (day, description, minutes, ticket, project) VALUES (?, ?, ?, ?, ?)",
        (day, description, minutes, ticket, project.upper()))
    cur.close()

    db.commit()
    db.close()

    latest(config, 0)


def load_configuration(config_file):
    """
    Load the configuration for this script
    :param config_file: the name of the config file
    :return: the configuration object
    """
    config = configparser.ConfigParser()
    config.read(config_file)
    return config


def remove(config):
    db = open_connection(config)
    cur = db.cursor()

    cur.execute("DELETE FROM timesheet WHERE id=(SELECT MAX(id) FROM timesheet)")
    cur.close()

    db.commit()
    db.close()

    latest(config, 0)


def main():
    """
    Parse the command line arguments and choose the right action to take
    """
    parser = argparse.ArgumentParser(description="Manage the timesheet database")
    parser.add_argument(
        "--config",
        default="timesheet.ini",
        type=str,
        help="the configuration file"
    )

    subcommands = parser.add_subparsers(dest="subcommand", title="subcommands")

    sync_subcommand = subcommands.add_parser('sync', help="download entries from Jira and Clockwork")
    sync_subcommand.add_argument(
        "--horizon", 
        dest="horizon", 
        type=int, 
        default=1,
        help="how many days should I go back when synchronizing the time entries from Jira")

    report_subcommand = subcommands.add_parser('report', help="report how much hours I worked on each day")
    report_subcommand.add_argument(
        "--horizon", 
        dest="horizon", 
        type=int, 
        default=3, 
        help="how many days should I go back")

    latest_subcommand = subcommands.add_parser('latest', help='show the latest time entries')
    latest_subcommand.add_argument(
        "--horizon", 
        dest="horizon", 
        type=int, 
        default=0, 
        help="how many days should I go back")

    create_subcommand = subcommands.add_parser('create', help='create a time entry manually')
    create_subcommand.add_argument(
        "project",
        help="the code of the project")
    create_subcommand.add_argument(
        "minutes",
        help="how much time this taken")
    create_subcommand.add_argument(
        "description",
        help="the description to put inside the database")
    create_subcommand.add_argument(
        "--ticket", 
        dest="ticket", 
        type=str, 
        default=None, 
        help="the ticket this is reported on (this is usually empty since "
            "when you have a ticket you log your time on the ticket)")
    create_subcommand.add_argument(
        "--day",
        type=str,
        default=datetime.date.today().strftime("%Y-%m-%d"),
        help="the day on which this entry should be stored, defaults to "
            "today")

    subcommands.add_parser('remove', help='remove the latest created time entry')

    args = parser.parse_args()

    config = load_configuration(args.config)

    if args.subcommand == "sync":
        sync(config, args.horizon)
    elif args.subcommand == "report":
        report(config, args.horizon)
    elif args.subcommand == "latest" or args.subcommand is None:
        latest(config, getattr(args, 'horizon', 0))
    elif args.subcommand == "create":
        create(config, args.project, args.minutes, args.description, ticket=args.ticket, day=args.day)
    elif args.subcommand == "remove":
        remove(config)


main()
