'''
    New York Times XBMC Addon
    ~~~~~~~~~~~~~~~~~~~~~~~~~

    Watch video from The New York Times.
    http://video.on.nytimes.com/

   :copyright: (c) 2012 by Jonathan Beluch
   :modified on 2014, 2015 by idleloop
   :license: GPLv3, see LICENSE.txt for more details.
'''
from xbmcswift2 import Plugin
from resources.lib import api

# plugin settings
import xbmcaddon
settings = xbmcaddon.Addon(id='plugin.video.newyorktimes')

plugin = Plugin()


@plugin.route('/')
def show_topics():
    '''The main menu, shows available video topics
    '''
    items = [{
        'label': name.replace('&amp;', "&"),
        'path': plugin.url_for('show_topic', url=url),
    } for name, url in api.get_topics()]
    return items


@plugin.route('/topics/<url>')
@plugin.route('/topics/<url>/<page>', name='show_topic_nextpage')
def show_topic(url, page='0'):
    '''For a given topic page, shows available sub-topics (if present) as well
    as videos.
    '''
    page = int(page)
    resolution_option = settings.getSetting("resolution")
    videos = api.get_videos( url, resolution_option, page )

    if (page==0):
        subtopics = [{
            'label': label,
            'path': plugin.url_for('show_topic', url=path),
        } for label, path in api.get_sub_topics(url)]
        videos=subtopics+videos

    # paginated results:
    videos.append({
            'label':    'Next >>',
            'path':     plugin.url_for( 'show_topic_nextpage', url=url, page=str(page+1) )
        })

    return videos


if __name__ == '__main__':
    plugin.run()
