#!/usr/bin/python

from __future__ import print_function

import argparse
import json
import logging
import mechanize
from urlparse import urlparse, urlunparse
import os
import re
import requests
from subprocess import call
import sys
import urllib2
import yaml

URLS = {
    'download': "https://www.save.tv/STV/M/obj/cRecordOrder/"
                "croGetDownloadUrl.cfm?TelecastId=%d&iFormat=%d&"
                "bAdFree=1",
    'archive': "https://www.save.tv/STV/M/obj/archive/JSON/"
               "VideoArchiveApi.cfm?iEntriesPerPage=%s&iCurrentPage=%s&"
               "iFilterType=1&sSearchString=&iTextSearchType=0&iChannelId=0&"
               "iTvCategoryId=%d&iTvSubCategoryId=0&bShowNoFollower=false&"
               "iRecordingState=1&sSortOrder=StartDateDESC&"
               "iTvStationGroupId=0&iRecordAge=0&iDaytime=0",
    'search': "https://www.save.tv/STV/M/obj/archive/JSON/"
              "VideoArchiveApi.cfm?iEntriesPerPage=%s&iCurrentPage=%s&"
              "iFilterType=1&sSearchString=%s&iTextSearchType=2&iChannelId=0&"
              "iTvCategoryId=%d&iTvSubCategoryId=0&bShowNoFollower=false&"
              "iRecordingState=1&sSortOrder=StartDateDESC&"
              "iTvStationGroupId=0&iRecordAge=0&iDaytime=0",
    'delete': "https://www.save.tv/STV/M/obj/cRecordOrder/croDelete.cfm?"
              "TelecastID=%d"
}


def initialize_logging():
    """Initialze the Logger."""
    logger = logging.getLogger(name='logger')
    formatter = logging.Formatter('%(asctime)s %(levelname)-8s %(message)s')
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logging.getLogger('logger')


def get_browser(username, password):
    browser = mechanize.Browser()
    browser.open('https://www.save.tv')
    browser.select_form(nr=0)
    browser.form["sUsername"] = str(username)
    browser.form["sPassword"] = str(password)
    browser.submit()
    return browser


def get_download_url(browser, tid):
    response = browser.open(URLS['download'] % (tid, 0))
    data = json.loads(response.get_data())
    url_details = data['ARRVIDEOURL']
    tid = url_details.pop()
    url_details.pop()
    url = urlparse(url_details.pop())
    return urlunparse(url._replace(query='m=dl'))


def delete_recording(browser, tid):
    return browser.open(URLS['delete'] % tid)


def load_configuration(filename):
    return yaml.load(open(filename, 'r'))


def parse_command_line_arguments():
    """Parse the command line arguments."""
    parser = argparse.ArgumentParser()

    parser.add_argument('--configuration', default='configuration.yaml',
                        help="Path to the onfiguration file.")

    parser.add_argument('--search', default=None,
                        help="Search for a specific title.")

    parser.add_argument('--category', default=0, type=int, choices=range(0,7),
                        help="Get recordings of a specific category. (0=All, "
                        "1=Movies, 2=Series, 3=Shows, 4=Sport, 5=Info, "
                        "6=Music)")

    parser.add_argument('--delete', action="store_true", default=False,
                        help="Delete recording after download.")

    parser.add_argument('--delete-duplicates', action="store_true",
                        default=False,
                        help="Delete duplicate recordings.")

    parser.add_argument('--force-delete', action="store_true", default=False,
                        help="Force delete of recordings.")

    parser.add_argument('--download', action="store_true", default=False,
                        help="Download recordings.")

    parser.add_argument('--force-download', action="store_true", default=False,
                        help="Force download of recordings.")

    parser.add_argument('--number', type=int, default=5,
                        help="Number of recordings.")

    parser.add_argument('--destination', default='target/',
                        help="Download destination path.")

    args = parser.parse_args()
    return (parser, args)


def get_filename(url):
    response = requests.head(url)
    filename = re.findall("filename=(\S+)",
                          response.headers['content-disposition'])
    clean_filename = re.findall("(\S+)_\d{4}-\d{2}-\d{2}_\d{4}_\d{6}\.mp4",
                                filename[0])
    return "%s.mp4" % clean_filename[0]


def register_download(filename, destination):
    with open(os.path.join(destination, "downloads.yaml"), "a+") as fp:
        print("- %s" % filename, file=fp)


def already_downloaded(filename, destination):
    try:
        downloads = yaml.load(open(os.path.join(destination, "downloads.yaml"), 'r'))
    except:
        return False
    return filename in downloads


def main():
    parser, args = parse_command_line_arguments()
    configuration = load_configuration(args.configuration)
    logger = initialize_logging()
    browser = get_browser(configuration['username'], configuration['password'])

    if args.search:
        search = urllib2.quote(args.search, '')
        response = browser.open(URLS['search'] %
                                (str(args.number), '1', search, args.category))
    else:
        response = browser.open(URLS['archive'] % (str(args.number), '1', args.category))

    data = json.loads(response.get_data())
    # total_pages = int(data['ITOTALPAGES'])
    # current_page = int(data['ICURRENTPAGE'])

    for entry in data['ARRVIDEOARCHIVEENTRIES']:
        deleted = False
        title = entry['STITLE']
        if 'STRTELECASTENTRY' in entry:
            # formats = entry['STRTELECASTENTRY']['ARRALLOWDDOWNLOADFORMATS']
            subtitle = entry['STRTELECASTENTRY']['SSUBTITLE']
            status = entry['STRTELECASTENTRY']['SSTATUS']
            tid = int(entry['STRTELECASTENTRY']['ITELECASTID'])
            free = bool(entry['STRTELECASTENTRY']['BDOWNLOADADFREE'])
        elif 'ARRALLOWDDOWNLOADFORMATS' in entry:
            # formats = entry['ARRALLOWDDOWNLOADFORMATS']
            subtitle = entry['SSUBTITLE']
            status = entry['SSTATUS']
            tid = int(entry['ITELECASTID'])
            free = bool(entry['BDOWNLOADADFREE'])

        url = get_download_url(browser, tid)

        logger.info("title = %s, subtitle = %s" % (title, subtitle))
        logger.info("tid = %d, status = %s, free = %s" % (tid, status, free))

        if status == 'OK' and (free or args.force_download):
            if args.download:
                logger.info("url = %s" % url)
                filename = get_filename(url)
                if not already_downloaded(filename, args.destination):
                    call(["wget", "-O",
                          os.path.join(args.destination, filename), url])
                    logger.info("filename = %s" % filename)
                    register_download(filename, args.destination)
                if args.delete:
                    deleted = True
                    delete_recording(browser, tid)

        if status == 'FAILED' and args.delete:
            deleted = True
            delete_recording(browser, tid)

        if not deleted and args.force_delete:
            delete_recording(browser, tid)

    return 0

if __name__ == '__main__':
    sys.exit(main())
