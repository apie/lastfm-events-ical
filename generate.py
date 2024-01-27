#!/usr/bin/env python3
# Scrape lastfm user event page for a specific year and generate an ical file for it
# By Apie
# 2024-01-25
import typer
from requests_html import HTMLSession

from os import path
from sys import argv
from icalendar import Event, Calendar
from datetime import timedelta, datetime
import pytz

timezone = "Europe/Amsterdam"
session = HTMLSession()


def get_events(username: str, year: str):
    # No year means upcoming events
    url = f"https://www.last.fm/user/{username}/events/{year}"
    r = session.get(url)
    for event in r.html.find("tr.events-list-item"):
        datetimestr = event.find("time", first=True).attrs.get("datetime")
        link = "https://www.last.fm" + event.find(
            "a.events-list-cover-link", first=True
        ).attrs.get("href")
        title = event.find(".events-list-item-event--title", first=True).text
        lineup = event.find(
            ".events-list-item-event--lineup", first=True
        ).text  # Does not include main act
        location = event.find(".events-list-item-venue", first=True).text
        date_obj = datetime.fromisoformat(datetimestr).date()
        yield date_obj, link, title, lineup, location


def print_events(username, year):
    for event in get_events(username, year):
        date_obj, link, title, lineup, location = event
        print(f"{date_obj=} {link=} {title=} {lineup=} {location=}")


def generate_ical(username: str, year: str = "", print_only: bool = False):
    if print_only:
        return print_events(username, year)

    cal = Calendar()
    cal.add("prodid", f"-//Last.fm events for {username} {year}//")
    cal.add("version", "2.0")

    now = datetime.now(pytz.timezone(timezone))

    for event_tuple in get_events(username, year):
        date_obj, link, title, lineup, location = event_tuple
        location = location.replace("\n", ", ")
        event = Event()
        event.add("uid", str(now) + title)
        event.add("summary", f"{title} at {location}")
        event.add("location", location)
        event.add("description", f"{title} + {lineup}. Link: {link}")
        event.add("dtstart", date_obj)
        event.add("dtend", date_obj + timedelta(days=1))
        event.add("dtstamp", now)
        cal.add_component(event)

    with open(
        path.join(
            path.dirname(path.realpath(argv[0])), f"lastfm_events_{username}_{year}.ics"
        ),
        "wb",
    ) as f:
        f.write(cal.to_ical())


if __name__ == "__main__":
    typer.run(generate_ical)
