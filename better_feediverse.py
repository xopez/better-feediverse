#!/usr/bin/env python3

import os
import re
import sys
import yaml
import argparse
import dateutil
import feedparser
import random
import time

from bs4 import BeautifulSoup
from mastodon import Mastodon
from datetime import datetime, timezone, MINYEAR
from tzlocal import get_localzone

DEFAULT_CONFIG_FILE = os.path.join("~", ".better_feediverse")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help=(
            "perform a trial run with no changes made: " "don't toot, don't save config"
        ),
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="be verbose")
    parser.add_argument(
        "-c",
        "--config",
        help="config file to use",
        default=os.path.expanduser(DEFAULT_CONFIG_FILE),
    )
    parser.add_argument(
        "-d",
        "--delay",
        action="store_true",
        help="delay randomly from 10 to 30 seconds between each post",
    )

    args = parser.parse_args()
    config_file = args.config

    if args.verbose:
        print("using config file", config_file)

    if not os.path.isfile(config_file):
        setup(config_file)

    config = read_config(config_file)

    masto = Mastodon(
        version_check_mode="none",
        api_base_url=config["url"],
        client_id=config["client_id"],
        client_secret=config["client_secret"],
        access_token=config["access_token"],
    )

    newest_post = config["updated"]

    for feed in config["feeds"]:

        try:
            feed["custom_http_headers"]
        except:
            http_headers = ""
        else:
            http_headers = "request_headers={" + config["custom_http_headers"] + "}"
            if args.verbose:
                print(f"HTTP headers: {config['custom_http_headers']}")

        if args.verbose:
            print(f"fetching {feed['url']} entries since {config['updated']}")

        for entry in get_feed(feed["url"], config["updated"], http_headers):
            newest_post = max(newest_post, entry["updated"])

            try:
                feed["ignoretitle"]
            except:
                ignoretitle = ""
            else:
                ignoretitle = feed["ignoretitle"].split(", ")
                if args.verbose:
                    print(f"ignoring {ignoretitle}")
                if any(x in entry["title"] for x in ignoretitle):
                    continue

            if args.verbose:
                print(entry)
            if args.dry_run:
                print("trial run, not tooting ", entry["title"][:50])
            if not args.dry_run:
                postbody = feed["template"].format(**entry)
                if len(postbody) > 499:
                    postfix = "…\n\n(more…)"
                    postbody = postbody[: (499 - len(postfix))] + postfix
#                masto.status_post(postbody, visibility="direct")
#                masto.status_post(postbody, visibility="private")
#                masto.status_post(postbody, visibility="unlisted")
                masto.status_post(postbody, visibility="public")
            if args.delay:
                delay = random.randrange(10, 30)
                print("Delaying..." + str(delay) + " seconds...")
                time.sleep(delay)

    if not args.dry_run:
        config["updated"] = newest_post.isoformat()
        save_config(config, config_file)


def get_feed(feed_url, last_update, http_headers):
    feed = feedparser.parse(feed_url, http_headers)
    if last_update:
        entries = [
            e for e in feed.entries if dateutil.parser.parse(e["updated"]) > last_update
        ]
    else:
        entries = feed.entries
    entries.sort(key=lambda e: e.updated_parsed)
    for entry in entries:
        yield get_entry(entry)


def get_entry(entry):
    hashtags = []
    for tag in entry.get("tags", []):
        t = tag["term"].replace(" ", "_").replace(".", "").replace("-", "")
        hashtags.append("#{}".format(t))
    author = entry.get("author", "")
    summary = entry.get("summary", "")
    content = entry.get("content", "") or ""
    if content:
        content = cleanup(content[0].get("value", ""))
    url = entry.id
    updatedZ = dateutil.parser.parse(entry["updated"])
    updatedLT= updatedZ.astimezone(get_localzone())

    return {
        "url": url,
        "link": entry.get("link", ""),
        "links": entry.get("links", ""),
        "title": cleanup(entry.title),
        "author": cleanup(author),
        "summary": cleanup(summary),
        "content": content,
        "hashtags": " ".join(hashtags),
        "updated": updatedZ,
        "updateddateZ": updatedZ.strftime('%Y%m%d'),
        "updateddateLT": updatedLT.strftime('%Y%m%d'),
        "updateddatetimeZ": updatedZ.strftime('%Y%m%d%H%M%S'),
        "updateddatetimeLT": updatedLT.strftime('%Y%m%d%H%M%S'),
        "updateddatetimeLTDE": updatedLT.strftime('%d.%m.%Y %H:%M')
    }


def cleanup(text):
    html = BeautifulSoup(text, "html.parser")
    text = html.get_text()
    text = re.sub("\xa0+", " ", text)
    text = re.sub("  +", " ", text)
    text = re.sub(" +\n", "\n", text)
    text = re.sub("\n\n\n+", "\n\n", text, flags=re.M)
    return text.strip()


def find_urls(html):
    if not html:
        return
    urls = []
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(["a", "img"]):
        if tag.name == "a":
            url = tag.get("href")
        elif tag.name == "img":
            url = tag.get("src")
        if url and url not in urls:
            urls.append(url)
    return urls


def yes_no(question):
    res = input(question + " [y/n] ")
    return res.lower() in "y1"


def save_config(config, config_file):
    copy = dict(config)
    with open(config_file, "w") as fh:
        fh.write(yaml.dump(copy, default_flow_style=False))


def read_config(config_file):
    config = {"updated": datetime(MINYEAR, 1, 1, 0, 0, 0, 0, timezone.utc)}
    with open(config_file) as fh:
        cfg = yaml.load(fh, yaml.SafeLoader)
        if "updated" in cfg:
            cfg["updated"] = dateutil.parser.parse(cfg["updated"])
    config.update(cfg)
    return config


def setup(config_file):
    url = input("What is your Mastodon Instance URL? ")
    have_app = yes_no("Do you have your app credentials already?")
    if have_app:
        name = "better_feediverse"
        client_id = input("What is your app's client id: ")
        client_secret = input("What is your client secret: ")
        access_token = input("access_token: ")
    else:
        print("Ok, I'll need a few things in order to get your access token")
        name = input("app name (e.g. better_feediverse): ")
        client_id, client_secret = Mastodon.create_app(
            api_base_url=url,
            client_name=name,
            # scopes=['read', 'write'],
            website="https://github.com/xopez/better_feediverse",
        )
        username = input("mastodon username (email): ")
        password = input("mastodon password (not stored): ")
        m = Mastodon(client_id=client_id, client_secret=client_secret, api_base_url=url)
        access_token = m.log_in(username, password)

    feed_url = input("RSS/Atom feed URL to watch: ")
    old_posts = yes_no("Shall already existing entries be tooted, too?")
    config = {
        "name": name,
        "url": url,
        "client_id": client_id,
        "client_secret": client_secret,
        "access_token": access_token,
        "feeds": [{"url": feed_url, "template": "{title} {url}"}],
    }
    if not old_posts:
        config["updated"] = datetime.now(tz=timezone.utc).isoformat()
    save_config(config, config_file)
    print("")
    print(
        "Your better_feediverse configuration has been saved to {}".format(config_file)
    )
    print("Add a line line this to your crontab to check every 15 minutes:")
    print("*/15 * * * * /usr/local/bin/better_feediverse")
    print("")


if __name__ == "__main__":
    main()
