'''
    resources.lib.api
    ~~~~~~~~~~~~~~~~~

    This module contains functions to interact with the NYT website and
    associated brightcove api for videos.

   :copyright: (c) 2012 by Jonathan Beluch
   :modified on 2014, 2015, 2018 by idleloop
   :license: GPLv3, see LICENSE.txt for more details.
'''
import urlparse
import urllib2
import re
import json
try:
    # //kodi.wiki/index.php?title=Add-on:Parsedom_for_xbmc_plugins
    from CommonFunctions import parseDOM, stripTags
except:
    from parsedom import parseDOM, stripTags
import xbmc

from xbmcswift2 import Plugin
plugin = Plugin()


BASE_URL        = 'https://www.nytimes.com/video/'
NYT_URL_BASE    = 'https://www.nytimes.com/'
NYT_REST_API_URL= 'https://www.nytimes.com/svc/video/api/v2/'
NYT_REST_API = { 'playlist': '?callback=timesVideoPageCollection',  # '&skip=0&count=30'
                 'video': '?callback=vhs_callback_',                # 'id' repeated
               }
ELEMENTS_PER_PAGE = 18
LATEST_VIDEOS = 'Latest Videos'


def _url(path):
    '''Returns an absoulte URL for the given path'''
    return urlparse.urljoin(BASE_URL, path)


def _get_html(url, retries=5):
    log('_get_html opening url "%s"' % url)
    req = urllib2.Request(url, None, { 'User-Agent' : 'Mozilla/5.0' })
    html = ''
    retry_counter=0
    RETRY_TIME = 1
    while True:
        try:
            html = urllib2.urlopen(req).read()
            log('_get_html received %d bytes' % len(html))
            break
        except urllib2.HTTPError as ex:
            log('_get_html error: %s' % ex)
            if (re.match(r'.+HTTP Error 301.+', str(ex))):
                raise
            dialog = xbmcgui.Dialog()
            dialog.notification( 'NYT',
                'waiting for remote server ...',
                xbmcgui.NOTIFICATION_INFO, int(RETRY_TIME*2000) )
            retry_counter += retry_counter
            time.sleep(RETRY_TIME + randint(0, 2*retries))
            pass
        if retry_counter >= retries:
            break
    return html


def log(msg):
    try:
        xbmc.log('NewYorkTimes: %s' % (
            msg
        ))
        #), level=xbmc.LOGNOTICE) # https://forum.kodi.tv/showthread.php?tid=324570
    except UnicodeEncodeError:
        xbmc.log('NewYorkTimes: %s' % (
            msg.encode('utf-8', 'ignore')
        ))
        #), level=xbmc.LOGNOTICE) # https://forum.kodi.tv/showthread.php?tid=324570


def get_topics():
    '''Returns a list of (topic_name, url) of available topics'''
    html = _get_html( BASE_URL )
    menu = parseDOM( html, 'div', attrs={ 'class': 'header-container[^\'"]*' } )
    topics_url = parseDOM( menu, 'a', ret='href' )
    topics_description = parseDOM( menu, 'a' )
    links_indexes =  [ x for x,y in enumerate(topics_url) if y.startswith('/video/') ]
    topics = [( stripTags( topics_description[i] ), NYT_URL_BASE + topics_url[i][1:] ) for i in links_indexes]
    topics.insert( 0, (LATEST_VIDEOS, _url('/video/latest-video/')) )
    return topics


def get_sub_topics(topic_url):
    '''Returns al ist of (topic_name, url) for sub topics available on the
    given topic page. If the provided url is a sub topic page, an empty list
    will be returned.
    '''
    html = _get_html( topic_url )
    topic_url = topic_url.replace( NYT_URL_BASE[0:-1], '' )
    try:
        json_text = re.search( r'var navData =(\[\{.+?\}\]\}\]);', html ).group(1)
    except:
        return []
    json_object = json.loads('{ "elements": ' + json_text + ' }')
    elements = json_object["elements"]
    topics = []
    for x,y in enumerate( reversed( elements ) ): # usually subtopics are at the end
        if re.search( y["publish_url"], topic_url ): # search because topic_url doesn't/shouldn't end in '/'...
            for i,j in enumerate( y["plst_secondary"] ):
                topics.append( ( j["display_name"], NYT_URL_BASE + j["publish_url"][1:] ) )
            break
    return topics


def get_videos(url, description, ref_id, resolution_option=0, page=0):
    '''For a given topic url, returns a list of associated videos using the
    nyt REST API.
    '''
    if ref_id == '':
        html = _get_html( url )
        menu = parseDOM( html, 'div', attrs={'class': 'recent-episodes'} )
        links = parseDOM( menu, 'a', attrs={'class': 'thumb-holder'} , ret='href')
        for i, link in enumerate( links ):
            # videos can be classified in more than one category and the main one may not b the one we're searching for (description)
            ref_id = link.split('=')[-1]
            videos = find_playlist_by_reference_id(ref_id, description, resolution_option, page)
            if videos != []:
                # correct classification! (json contains Show display_name == description)
                break
    else:
        # time not wasted examining various json urls, as we know that the received ref_id is good
        videos = find_playlist_by_reference_id(ref_id, description, resolution_option, page)
    return ( videos, ref_id )


def find_playlist_by_reference_id(ref_id, description, resolution_option, page=0):
    '''From a given ref_id, returns a list of associated videos using the
    nyt REST API.
    '''
    url = NYT_REST_API_URL + 'playlist/' + ref_id + NYT_REST_API["playlist"] + \
        '&skip=' + str(page*ELEMENTS_PER_PAGE) + \
        '&count=' + str(ELEMENTS_PER_PAGE)
    json_object = obtain_json(url, description)
    if json_object == []:
        # this video id is classified in more than one category and the main one is not the one we're searching for (description)
        return []
    videos = json_object["videos"]
    items=[]
    for video in videos:
        url = NYT_REST_API_URL + 'video/' + str(video["id"]) + NYT_REST_API["video"] + str(video["id"])
        json_object = obtain_json(url)
        items.append( item_from_video(json_object, resolution_option) )
    return items


def obtain_json(url, description=''):
    # obtain json from url and scrape js from it
    json_text = urllib2.urlopen(url).read()
    if description != '' and description != LATEST_VIDEOS:
        if '"display_name":"' + description.encode('ascii', 'ignore') not in json_text:
            # this video id is classified in more than one category and the main one is not the one we're searching for (description)
            return []
    try:
        json_text = re.compile( r'^[^\{]+(.+)\);$', re.DOTALL ).findall(json_text)[0]
        json_object = json.loads(json_text)
    except:
        return []
    return json_object


def item_from_video(video, resolution_option):
    '''Returns a dict suitable for passing to plugin.add_items.
    '''
    # extract the best possible resolution from renditions[] given the resolution_option option:
    url=''
    signal=0
    try:
        for rendition in video["renditions"]:
            # select only the more compatible codecs:
            if ( not re.match( 'h264', rendition["video_codec"], re.IGNORECASE ) ):
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