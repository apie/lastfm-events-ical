#!/usr/bin/env python3
# Scrape lastfm user event page for a specific year and generate an ical file for it
# By Apie
# 2024-01-25
import typer
from requests_html import HTMLSession

from os import path
from pathlib import Path
from sys import argv
from icalendar import Event, Calendar
from datetime import timedelta, datetime, date
import pytz
import time
import json

timezone = "Europe/Amsterdam"


class SimpleCache:
    CACHE_DIR = Path("/tmp/lfm-ical")
    CACHE_DIR.mkdir(exist_ok=True)

    def get(self, name):
        def object_hook(obj):
            _isoformat = obj.get("_isoformat")
            if _isoformat is not None:
                return date.fromisoformat(_isoformat)
            return obj

        cached = self.CACHE_DIR / name
        if cached.exists():
            return json.loads(cached.read_bytes(), object_hook=object_hook)
        return False

    def set(self, name, content):
        def default(obj):
            if isinstance(obj, date):
                return {"_isoformat": obj.isoformat()}
            raise TypeError("...")

        cached = self.CACHE_DIR / name
        cached.write_text(json.dumps(content, default=default))


class LfmEventGetter:
    use_cache: False

    def __init__(self, use_cache):
        self.use_cache = use_cache
        self.session = HTMLSession()
        self.session.headers["User-Agent"] = "lfm ical"
        self.cache = SimpleCache() if use_cache else None

    def _cached_get_events(self, username: str, year: str):
        cached = self.cache.get(f"get_events_{username}_{year}")
        if cached:
            # print("Reading from cache")
            return cached
        result = list(self._get_events(username, year))
        self.cache.set(f"get_events_{username}_{year}", result)
        return result

    def get_events(self, username: str, year: str):
        if self.use_cache:
            return self._cached_get_events(username, year)
        return self._get_events(username, year)

    def _get_events(self, username: str, year: str):
        # No year means upcoming events
        base_url = f"https://www.last.fm/user/{username}/events/{year}"
        url = base_url
        page_no = 1
        while True:
            # print('getting page', page_no, 'url', url)
            r = self.session.get(url)
            # print(r)
            r.raise_for_status()
            if r.status_code == 600:
                raise Exception("Server overloaded, try again later.")
            yield from self.get_events_from_page(r.html)
            next_page = r.html.find("li.pagination-next>a", first=True)
            if next_page:
                url = base_url + next_page.attrs.get("href")
                page_no += 1
                time.sleep(1)
            else:
                break

    def get_events_from_page(self, html):
        for event in html.find("tr.events-list-item"):
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

    def print_events(self, username, year):
        for event in self.get_events(username, year):
            date_obj, link, title, lineup, location = event
            print(f"{date_obj=} {link=} {title=} {lineup=} {location=}")


def generate_ical(
    username: str, year: str = "", print_only: bool = False, use_cache: bool = False
):
    getter = LfmEventGetter(use_cache)
    if print_only:
        return getter.print_events(username, year)

    cal = Calendar()
    cal.add("prodid", f"-//Last.fm events for {username} {year}//")
    cal.add("version", "2.0")

    now = datetime.now(pytz.timezone(timezone))

    for event_tuple in getter.get_events(username, year):
        date_obj, link, title, lineup, location = event_tuple
        location = location.replace("\n", ", ")
        event = Event()
        event.add("uid", str(now) + title + str(date_obj))
        event.add("summary", f"{title} at {location}")
        event.add("location", location)
        event.add("description", f"{title} + {lineup}. Link: {link}")
        event.add("dtstart", date_obj)
        event.add("dtend", date_obj + timedelta(days=1))
        event.add("dtstamp", now)
        cal.add_component(event)

    Path(path.join(path.dirname(path.realpath(argv[0])), "..", "data")).mkdir(
        exist_ok=True
    )
    with open(
        path.join(
            path.dirname(path.realpath(argv[0])),
            "..",
            "data",
            f"lastfm_events_{username}_{year}.ics",
        ),
        "wb",
    ) as f:
        f.write(cal.to_ical())


if __name__ == "__main__":
    typer.run(generate_ical)
