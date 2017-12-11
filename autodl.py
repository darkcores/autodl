#!/usr/bin/env python3
'''This script gets an RSS feed, extracts urls and matches titles to a
list of strings to download on a remote server running transmission
with RPC enabled.

'''
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
from email.message import EmailMessage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('autodl')
db = None
added = []
done = []


def initdb():
    """Initialize database"""
    global db
    if not os.path.isfile("autodl.db"):
        logger.info("Initialising database")
        db = sqlite3.connect('autodl.db')
        c = db.cursor()
        c.execute('''CREATE TABLE torrents (
        date text,
        title text,
        url text,
        done boolean,
        hash text)''')
        date = datetime.datetime.now().replace(microsecond=0).isoformat()
        c.execute('''INSERT INTO torrents VALUES(?, "init", "init",
        1, "init")''', (date,))
        db.commit()
    else:
        db = sqlite3.connect('autodl.db')


def sendmail(msg):
    """Send email message"""
    server = smtplib.SMTP(config.SMTPSERVER)
    m = EmailMessage()
    m.set_content(msg)
    m['Subject'] = 'Torrent status update'
    m['From'] = config.MAILFROM
    m['To'] = config.MAILTO
    server.send_message(m)
    server.quit()


def check_date(data):
    """Check if we already have a a newer dat in out database"""
    global db
    c = db.cursor()
    datefmt = "%a, %d %b %Y %X %z"
    date = datetime.datetime.strptime(data['published'],
                                      datefmt).isoformat()[:19]
    c.execute("SELECT * FROM torrents WHERE datetime(date)<=datetime(?)",
              (date,))
    lc = len(c.fetchall())
    # print("Length fetch: %s" % lc)
    return lc == 0


def update_feed():
    """Get feeds and add to list of urls to add to transmission."""
    global added
    for feed in config.FEEDS:
        fp = feedparser.parse(feed)
        for entry in fp['entries']:
            for substr in config.ACCEPTS:
                if substr in entry['title']:
                    if check_date(entry):
                        add_torrent(entry)
                        added.append(entry['title'])


def add_torrent(data):
    """Add torrent to transmission."""
    global db
    c = db.cursor()
    srv = transmissionrpc.Client(config.SERVER, port=config.PORT,
                                 user=config.USER, password=config.PASSWORD)
    url = data['link']
    title = data['title']
    logger.info("Adding url: %s" % title)
    t = srv.add_torrent(url,
                        download_dir='/media/downloads/automated/')
    thash = t.hashString
    datefmt = "%a, %d %b %Y %X %z"
    date = datetime.datetime.strptime(data['published'],
                                      datefmt).isoformat()[:19]
    c.execute("INSERT INTO torrents VALUES(?, ?, ?, 0, ?)", (date,
                                                             title,
                                                             url, thash))
    db.commit()


def check_done():
    """Check which torrents are done and remove."""
    global db
    global done
    c = db.cursor()
    srv = transmissionrpc.Client(config.SERVER, port=config.PORT,
                                 user=config.USER, password=config.PASSWORD)
    torrents = srv.get_torrents()
    c.execute("SELECT * FROM torrents WHERE done=0")
    for t in c.fetchall():
        for torrent in torrents:
            if torrent.hashString == t[4]:
                td = torrent
        if td.status == 'seeding':
            done.append(t[1])
            logger.info("Done: %s" % t[1])
            srv.remove_torrent(td.id)
            c.execute('''UPDATE torrents SET done=1 WHERE hash=?''',
                      (td.hashString,))
    db.commit()


def notify_mail():
    """Send a mail with data that has changed"""
    global added
    global done
    if len(added) == len(done) == 0:
        return
    logger.info("Sending mail with changes")
    msg = "Added torrents:\n"
    for t in added:
        msg += "    - %s\n" % t
    msg += "\nTorrents done:\n"
    for t in done:
        msg += "    - %s\n" % t
    sendmail(msg)
    added = []
    done = []


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
        notify_mail()
        logger.info("Sleeping")
        time.sleep(config.TIMEOUT*60)
