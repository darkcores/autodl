#!/usr/bin/env python3

import config
import smtplib
import transmissionrpc
import feedparser
import sqlite3
import logging
import time
import os
import sys
import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
db = None


def initdb():
    """Initialize database"""
    global db
    if not os.path.isfile("autodl.db"):
        logger.info("Initialising database")
        db = sqlite3.connect('autodl.db')
        c = db.cursor()
        c.execute('''CREATE TABLE torrents (date char(26), title text, url text, done
             boolean)''')
        date = datetime.datetime.now().isoformat()
        c.execute('''INSERT INTO torrents VALUES(?, "init", "init",
        1)''', (date,))
        db.commit()
    else:
        db = sqlite3.connect('autodl.db')


def update_feed():
    """Get feeds and add to list of urls to add to transmission."""
    for feed in config.FEEDS:
        fp = feedparser.parse(feed)
        for entry in fp['entries']:
            for substr in config.ACCEPTS:
                if substr in entry['title']:
                    for link in entry['links']:
                        add_url(link)


def add_url(data):
    """Add urls to transmission."""
    logger.info("Adding url")
    srv = transmissionrpc.Client(config.SERVER, port=config.PORT,
                                 user=config.USER, password=config.PASSWORD)


def check_done():
    """Check which torrents are done and remove."""
    srv = transmissionrpc.Client(config.SERVER, port=config.PORT,
                                 user=config.USER, password=config.PASSWORD)


if __name__ == '__main__':
    initdb()
    if db is None:
        logger.error("Could not open/create database")
        sys.exit(1)
    while True:
        logger.info("Updating feed")
        update_feed()
        logger.info("Checking torrent status")
        check_done()
        logger.info("Sleeping")
        time.sleep(config.TIMEOUT*60)
