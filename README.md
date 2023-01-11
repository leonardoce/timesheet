# Timesheet

I use this simple Python script to download data from
[Jira](https://jira.atlassian.com/) and
[Clockwork](https://www.herocoders.com/apps/clockwork-automated-timesheets-free)
and put them in local SQLite database.

The database can be used for reporting and statistics. Sometimes it's really
surprising to know on which project you really put your effort.


## Setup

You need to copy `timesheet.ini.template` to `timesheet.ini` and fill in the
details:

- `jira account id` can be discovered by clicking on your profile on the Jira 
	sidebar and by looking at the last URL component (i.e.
	https://********.atlassian.net/people/5bb7ad0ccc53fd0760103780, look at [this
	Jira community question](1)

- `jira account name` is in the same profile page and usually correspond to
	your email

- `jira token` need to be set looking at the instructions at [the atlassian
	documentation](2)

- `clockwork for jira token` can be created looking at the instructions at [the
	clockwork documentation](3)
	
- `endpoint` is the URL where your Jira instance is hosted	

[1]: https://community.atlassian.com/t5/Jira-questions/where-can-i-find-my-Account-ID/qaq-p/976527
[2]: https://support.atlassian.com/atlassian-account/docs/manage-api-tokens-for-your-atlassian-account/
[3]: https://herocoders.atlassian.net/wiki/spaces/CLK/pages/2999975967/Use+the+Clockwork+API

## How to download the existing data

This will synchronize the latest 30 days

```
./timesheet.py sync --horizon=30
```

## How to extract your timesheet

```
./timesheet.py latest --horizon=7
```
