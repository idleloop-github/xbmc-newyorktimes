'''
    New York Times XBMC Addon
    ~~~~~~~~~~~~~~~~~~~~~~~~~

    Watch video from The New York Times.
    http://video.on.nytimes.com/

   :copyright: (c) 2012 by Jonathan Beluch
   :modified on 2014, 2015 by idleloop
   :license: GPLv3, see LICENSE.txt for more details.
'''
from resources.lib import api
import xbmcgui

# plugin settings
import xbmcaddon
settings = xbmcaddon.Addon(id='plugin.video.newyorktimes')

from xbmcswift2 import Plugin
plugin = Plugin()

NYT_URL_BASE = 'https://www.nytimes.com/'

# persistent storage to store ref_id of representative videos for each NYT topic
# https://kodi.wiki/view/Add-on:Common_plugin_cache
try:
   import StorageServer
except:
   import storageserverdummy as StorageServer
cache = StorageServer.StorageServer("plugin.video.newyorktimes", 24) # plugin name, Cache time in hours


def global_items():
    return api.get_topics()


def global_items_ref_id_storage(description='', ref_id=''):
    # global_items_ref_id = {'this nyt topic description': 'has this ref_id video representative'}
    global_items_ref_id = cache.get( "global_items_ref_id" )
    if global_items_ref_id != '':
        global_items_ref_id = eval( global_items_ref_id )
    else:
        global_items_ref_id = {}
    if description != '':
        global_items_ref_id[description] = ref_id
        cache.set( "global_items_ref_id", repr( global_items_ref_id ) )
        return 1
    else:
        if repr(global_items_ref_id) == '{}':
            cache.set( "global_items_ref_id", repr( {} ) )
        return global_items_ref_id


@plugin.route('/')
def show_topics():
    '''The main menu, shows available video topics
    '''
    items = [ {
        'label': name.replace('&amp;', "&"),
        'path': plugin.url_for('show_topic', url=url),
    } for name, url in global_items() ]
    return items


@plugin.route('/topics/<url>')
@plugin.route('/topics/<url>/<page>', name='show_topic_nextpage')
def show_topic(url, page='0'):
    '''For a given topic page, shows available sub-topics (if present) as well
    as videos.
    '''
    page = int(page)
    resolution_option = settings.getSetting("resolution")

    # obtain description of this url topic, in order to correctly select videos from NYT API
    try:
        description = [y[0] for x,y in enumerate( global_items() ) if y[1] == url][0]
    except:
        description = '' # subcategory

    global_items_ref_id = global_items_ref_id_storage()

    dialog = xbmcgui.Dialog()
    dialog.notification( 'Retrieving videos.',
        'Please, wait ...',
        xbmcgui.NOTIFICATION_INFO, 5000 )

    ( videos, ref_id ) = api.get_videos( url,
        description,
        global_items_ref_id[description] if description in global_items_ref_id else '',
        resolution_option,
        page )

    # store ref_id representative of this url topic not to repeat unnecessary browsing
    if description != '' and not description in global_items_ref_id:
        global_items_ref_id_storage( description, ref_id )

    if (page==0):
        subtopics = [{
            'label': label,
            'path': plugin.url_for('show_topic', url=path),
        } for label, path in api.get_sub_topics(url)]
        videos=subtopics+videos

    # paginated results:
    if description != 'New York':
        # ('New York' section does not have direct correspondent json classification, and so, Next can't be calculated)
        videos.append({
                'label':    'Next >>',
                'path':     plugin.url_for( 'show_topic_nextpage', url=url, page=str(page+1) )
            })

    return videos


if __name__ == '__main__':
    plugin.run()
