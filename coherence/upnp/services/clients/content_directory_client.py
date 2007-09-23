# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright (C) 2006 Fluendo, S.A. (www.fluendo.com).
# Copyright 2006, Frank Scholz <coherence@beebits.net>

import sys, threading

from twisted.internet import reactor, defer
from twisted.python import log

from coherence.upnp.core import DIDLLite
from coherence.upnp.core import utils

global work, pending
work = []
pending = {}


class ContentDirectoryClient:

    def __init__(self, service):
        self.service = service
        self.namespace = service.get_type()
        self.url = service.get_control_url()
        self.service.subscribe()
        #print "ContentDirectoryClient __init__", self.url

    #def __del__(self):
    #    print "ContentDirectoryClient deleted"
    #    pass

    def remove(self):
        self.service.remove()
        self.service = None
        self.namespace = None
        self.url = None
        del self

    def subscribe_for_variable(self, var_name, callback):
        self.service.subscribe_for_variable(var_name, instance=0, callback=callback)

    def get_search_capabilities(self):
        action = self.service.get_action('GetSearchCapabilities')
        return action.call()

    def get_sort_extension_capabilities(self):
        action = self.service.get_action('GetSortExtensionCapabilities')
        return action.call()

    def get_feature_list(self):
        action = self.service.get_action('GetFeatureList')
        return action.call()

    def get_system_update_id(self):
        action = self.service.get_action('GetSystemUpdateID')
        return action.call()

    def browse(self, object_id=0, browse_flag='BrowseDirectChildren',
               filter='*', sort_criteria='',
               starting_index=0, requested_count=0):

        def process_result(result):
            #print result
            r = {}
            r['number_returned'] = result['NumberReturned']
            r['total_matches'] = result['TotalMatches']
            r['update_id'] = result['UpdateID']
            r['items'] = {}
            elt = DIDLLite.DIDLElement.fromString(result['Result'])
            for item in elt.getItems():
                #print "process_result", item
                i = {}
                i['upnp_class'] = item.upnp_class
                i['id'] =  item.id
                i['title'] =  item.title
                i['parent_id'] =  item.parentID
                if hasattr(item,'childCount'):
                    i['child_count'] =  str(item.childCount)
                if hasattr(item,'date') and item.date:
                    i['date'] =  item.date
                if hasattr(item,'albumArtURI') and item.albumArtURI:
                    i['album_art_uri'] = item.albumArtURI
                if hasattr(item,'res'):
                    resources = {}
                    for res in item.res:
                        url = res.data
                        resources[url] = res.protocolInfo
                    if len(resources):
                        i['resources']= resources
                r['items'][item.id] = i
            return r

        action = self.service.get_action('Browse')
        d = action.call( ObjectID=object_id,
                            BrowseFlag=browse_flag,
                            Filter=filter,SortCriteria=sort_criteria,
                            StartingIndex=str(starting_index),
                            RequestedCount=str(requested_count))
        d.addCallback( process_result)
        return d

    def search(self, container_id, criteria, starting_index=0,
               requested_count=0):
        #print "search:", criteria
        starting_index = str(starting_index)
        requested_count = str(requested_count)
        action = self.service.get_action('Search')
        d = action.call( ContainerID=container_id,
                            SearchCriteria=criteria,
                            Filter="*",
                            StartingIndex=starting_index,
                            RequestedCount=requested_count,
                            SortCriteria="")
        d.addErrback(self._failure)

        def gotResults(results):
            items = []
            if results is not None:
                elt = DIDLLite.DIDLElement.fromString(results['Result'])
                items = elt.getItems()
            return items

        d.addCallback(gotResults)
        return d

    def dict2item(self, elements):
        upnp_class = DIDLLite.upnp_classes.get(elements.get('upnp_class',None),None)
        if upnp_class is None:
            return None

        del elements['upnp_class']
        item = upnp_class(id='',
                          parentID=elements.get('parentID',None),
                          title=elements.get('title',None),
                          restricted=elements.get('restricted',None))
        for k, v in elements.items():
            attribute = getattr(item, k, None)
            if attribute is None:
                continue
            attribute = v

        return item

    def create_object(self, container_id, elements):
        if isinstance(elements, dict):
            elements = self.dict2item(elements)
        if isinstance(elements,DIDLLite.Object):
            didl = DIDLLite.DIDLElement()
            didl.addItem(elements)
            elements=didl.toString()
        if elements is None:
            elements = ''
        action = self.service.get_action('CreateObject')
        return action.call( ContainerID=container_id,
                            Elements=elements)

    def destroy_object(self, object_id):
        action = self.service.get_action('DestroyObject')
        return action.call( ObjectID=object_id)

    def update_object(self, object_id, current_tag_value, new_tag_value):
        action = self.service.get_action('UpdateObject')
        return action.call( ObjectID=object_id,
                            CurrentTagValue=current_tag_value,
                            NewTagValue=new_tag_value)

    def move_object(self, object_id, new_parent_id):
        action = self.service.get_action('MoveObject')
        return action.call( ObjectID=object_id,
                            NewParentID=new_parent_id)

    def import_resource(self, source_uri, destination_uri):
        action = self.service.get_action('ImportResource')
        return action.call( SourceURI=source_uri,
                            DestinationURI=destination_uri)

    def export_resource(self, source_uri, destination_uri):
        action = self.service.get_action('ExportResource')
        return action.call( SourceURI=source_uri,
                            DestinationURI=destination_uri)

    def delete_resource(self, resource_uri):
        action = self.service.get_action('DeleteResource')
        return action.call( ResourceURI=resource_uri)

    def stop_transfer_resource(self, transfer_id):
        action = self.service.get_action('StopTransferResource')
        return action.call( TransferID=transfer_id)

    def get_transfer_progress(self, transfer_id):
        action = self.service.get_action('GetTransferProgress')
        return action.call( TransferID=transfer_id)

    def create_reference(self, container_id, object_id):
        action = self.service.get_action('CreateReference')
        return action.call( ContainerID=container_id,
                            ObjectID=object_id)


    def _failure(self, error):
        log.msg(error.getTraceback(), debug=True)
        error.trap(Exception)
