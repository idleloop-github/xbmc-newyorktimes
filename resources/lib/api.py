'''
    resources.lib.api
    ~~~~~~~~~~~~~~~~~

    This module contains functions to interact with the NYT website and
    associated brightcove api for videos.

   :copyright: (c) 2012 by Jonathan Beluch
   :modified on 2014, 2015 by idleloop
   :license: GPLv3, see LICENSE.txt for more details.
'''
import urlparse
from resources.lib import requests
import re
from resources.lib.beautifulsoup import BeautifulSoup as BS
from core import scrapertools
from core import logger

from xbmcswift2 import Plugin
plugin = Plugin()

BASE_URL        = 'http://www.nytimes.com/video/'
NYT_URL_BASE    = 'http://www.nytimes.com/'
NYT_REST_API_URL= 'http://www.nytimes.com/svc/video/api/v2/'
NYT_REST_API = { 'playlist': '?callback=timesVideoPageCollection',  # '&skip=0&count=30'
                 'video': '?callback=vhs_callback_',                # 'id' repeated
               }
ELEMENTS_PER_PAGE = 18


def _url(path):
    '''Returns an absoulte URL for the given path'''
    return urlparse.urljoin(BASE_URL, path)


def get_topics():
    '''Returns a list of (topic_name, url) of available topics'''
    html = BS(requests.get(BASE_URL).text)
    menu = html.find('div', {'class': 'header-container'})
    links = menu.findAll('a', href=lambda h: h.startswith('/video/'))
    topics = [(a.text, _url(a['href'])) for a in links]
    topics.insert( 0, ('Latest Videos', _url('/video/latest-video/')) )
    return topics


def get_sub_topics(topic_url):
    '''Returns al ist of (topic_name, url) for sub topics available on the
    given topic page. If the provided url is a sub topic page, an empty list
    will be returned.
    '''
    html = BS(requests.get(topic_url).text)
    menu = html.find('div', {'class': 'main wrapper clearfix'})
    menu2 = menu.findAll('li', itemtype='http://schema.org/SiteNavigationElement')
    links = [menu3.find('a', href=lambda h: h.startswith('/video/')) for menu3 in menu2]

    if menu.find('li', {'class': 'active'}):
        # Viewing a sub-topic page, don't return sub topics again
        return []
    
    return [(a.text, _url(a['href'])) for a in links]


def get_videos(url, resolution_option, page=0):
    '''For a given topic url, returns a list of associated videos using the
    nyt REST API.
    '''
    html = BS(requests.get(url).text)
    menu = html.find('div', {'class': 'recent-episodes'})
    link = menu.find('a', {'class': 'thumb-holder'})
    ref_id = (link['href']).split('=')[-1]
    videos = find_playlist_by_reference_id(ref_id, resolution_option, page)
    return videos


def find_playlist_by_reference_id(ref_id, resolution_option, page=0):
    '''From a given ref_id, returns a list of associated videos using the
    nyt REST API.
    '''
    url = NYT_REST_API_URL + 'playlist/' + ref_id + NYT_REST_API["playlist"] + \
        '&skip=' + str(page*ELEMENTS_PER_PAGE) + \
        '&count=' + str(ELEMENTS_PER_PAGE)
    json_object = obtain_json(url)
    videos = json_object["videos"]
    items=[]
    for video in videos:
        url = NYT_REST_API_URL + 'video/' + video["id"] + NYT_REST_API["video"] + video["id"]
        json_object = obtain_json(url)
        items.append( item_from_video(json_object, resolution_option) )
    return items

def obtain_json(url):
    # obtain json from url and scrape js from it
    json_text = scrapertools.cache_page(url)
    try:
        json_text = re.compile( r'^[^\{]+(.+)\);$', re.DOTALL ).findall(json_text)[0]
        json_object = load_json(json_text)
    except:
        return []
    return json_object


def load_json(data):
    # callback to transform json string values to utf8
    def to_utf8(dct):
        rdct = {}
        for k, v in dct.items() :
            if isinstance(v, (str, unicode)) :
                rdct[k] = v.encode('utf8', 'ignore')
            else :
                rdct[k] = v
        return rdct
    try :        
        import json
        json_data = json.loads(data, object_hook=to_utf8)
        return json_data
    except:
        import sys
        for line in sys.exc_info():
            logger.error( "%s" % line ) 


def item_from_video(video, resolution_option):
    '''Returns a dict suitable for passing to plugin.add_items.
    '''
    # extract the best possible resolution from renditions[] given the resolution_option option:
    url=''
    signal=0
    try:
        for rendition in video["renditions"]:
            # select only the more compatible codecs:
            if (rendition["video_codec"] != 'H264'):
                continue
            height=int(rendition["height"])
            if (resolution_option == '0'):
                if (height<500):
                    if (height>signal):
                        signal=height
                        url=rendition["url"]
            elif (resolution_option == '1'):
                if (height>500 and height<800):
                    if (height>signal):
                        signal=height
                        url=rendition["url"]
            else:
                if (height>signal):
                    signal=height
                    url=rendition["url"]
        item = {
            'label': video["headline"],
            'path': url,
            'info': info_from_video(video),
            'is_playable': True,
        }
    except:
        return []

    try:
        for image in video["images"]:
            #if (int(image["width"]) > 250 and int(image["width"])< 500):
            if (image["type"] == 'videoSixteenByNine310'):
                item.update({ 'thumbnail': NYT_URL_BASE + image["url"] })
                break
    except:
        pass

    return item


def info_from_video(video):
    '''Returns an info dict for a video item.
    '''
    return {
        'year': video["publication_date"][:4],
        'plot': video["summary"],
        'plotoutline': video["headline"],
        'title': video["headline"],
        'premiered': video["publication_date"],
    }