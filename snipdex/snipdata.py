#!/usr/bin/env python
"""
snipdata.py: Snipdex data structures for a snippets, 
peers, zombi peers (fallbacks) and private options.

The contents of this file are subject to the PfTijah Public License 
Version 1.1 (the "License"); you may not use this file except in 
compliance with the License. You may obtain a copy of the License at 
http://dbappl.cs.utwente.nl/Legal/PfTijah-1.1.html

Software distributed under the License is distributed on an "AS IS" 
basis, WITHOUT WARRANTY OF ANY KIND, either express or implied. See 
the License for the specific language governing rights and limitations 
under the License.

The Original Code is the SnipDex system.

The Initial Developer of the Original Code is the "University of 
Twente". Portions created by the "University of Twente" are 
Copyright (C) 2012 "University of Twente". All Rights Reserved.

Authors: Almer Tigelaar
         Djoerd Hiemstra 
"""

import urllib
import hashlib
import sqlite3
import datetime
import random
import re
from operator import itemgetter
from xml.sax import saxutils # For escaping xml output

# local import
import html

SNIPPET_MAX_TITLE_LENGTH        = 256
SNIPPET_MAX_SUMMARY_LENGTH      = 512 
SNIPPET_MAX_EXT_SUMMARY_LENGTH  = 2048
SNIPDEX_RESPONSE_VERSION        = "0.2"

SNIPDEX_QUERY_REGISTER = 'snipdexiamback'
SNIPDEX_QUERY_PONG     = 'snipdexgoodtoseeyou'
SNIPDEX_QUERY_MYSELF   = 'snipdexwhoami'

#
# Some general tools first
#

def right_now():
   """Returns the current UTC datetime in Python format (yyyy-mm-dd hh:mm:ss)"""
   now = str(datetime.datetime.utcnow())
   return now[:now.rfind(".")]


def new_random_id():
    """Returns a random peer identifier
       @return               Sequence of 24 random characters"""
    characters = "".join(chr(i) for i in range(48,58) + range(65,91) + range(97,123))
    return "".join(random.choice(characters) for i in range(0, 23))


def html_template_to_url(html_template_url):
    """Returns the action link for a form
       @param html_template  Search template in case of Zombi peer
       @return               Absolute location
    """
    url = html_template_url.split('?', 1)[0]
    url = url.split('#', 1)[0]
    return url


def resolve_location(html_template, link, title=''):
    """Returns an absolute link for each search location
       @param html_template  Search template in case of Zombi peer
       @param title          Search result title
       @param link           Search result location
       @return               Absolute location
    """
    if not link: 
        if html_template:  # no link, so fill query in template
            return Query({'q': title}).fill_template_url(html_template)  
        else:              # no link nor template, so fill query in Snipdex
            return '?q=' + urllib.quote_plus(title)  
    elif link.find('://') != -1:  # all is well
        return link 
    elif html_template:   # we have a relative url
        (scheme, sep, url) = html_template.partition('://');
        (website, sep, get) = url.partition('/');
        website = scheme + '://' + website
        if link.startswith('/'):
            return website + link
        elif link.startswith('?'):
           (webdir, sep, get) = url.rpartition('?');
           webdir = scheme + '://' + webdir
           return webdir + link
        else:
           (webdir, sep, get) = url.rpartition('/');
           webdir = scheme + '://' + webdir
           return webdir + '/' + link
    else:
        return '' # Maybe raise an exception instead?

#
#  XML response
#

def snipdex_response(query, peer_list, snippet_list):
    """Outputs XML version of the search results.
    """
    result  = u'<snipdex_response version=' + saxutils.quoteattr(SNIPDEX_RESPONSE_VERSION) + '>\n'
    result += '<query '
    for key in query:
        result += key + '=' + saxutils.quoteattr(str(query[key])) + ' '
    result += '/>\n' 

    result += '<peers>\n'
    for (peer, status, score) in peer_list:
        result += peer.snipdex_response_peer(status, score)
    result += '</peers>\n'

    result += '<snippets>\n'
    for snippet in snippet_list:
        result += snippet.snipdex_response_snippet()
    result += '</snippets>\n'
    result += '</snipdex_response>'
    return result 


#
# Classes
#


class SnipdexCache(object):
    """Caches peers and snippets. 
    """

    __slots__ = [ "cache", "logger", "known_peers"]

    def __init__(self, filename, logger):
        """Creates the Snipdex cache
           snippets: two column table with (query, snippet_list) 
                      query with '#' are like vertical '#video' (inspired by Blekko, Twitter)?
                      query with '$' are languages '$nl'?
           peers:     two column table with (pid, peer)
                      (to be kept in memory also)

           @file  filename for cache
        """
        self.cache       = sqlite3.connect(filename)
        self.logger      = logger
        self.known_peers = dict()
        c = self.cache.cursor()
        try:
            c.execute("select * from peers")
        except sqlite3.OperationalError:
            self.logger.warning("Creating new cache at: " + filename)
            c.execute("create table peers (pid text primary key, peer text)")  # TODO: primary keys?
            c.execute("create table snippets (query text primary key, response text)")
            self.cache.commit()
            pid = new_random_id()          
            self.insert_response(Query({'q': SNIPDEX_QUERY_MYSELF}), PeerList(Peer(pid=pid)), SnippetList())
        else:
            for row in c:       # load all peers in memory
                peer = eval(row[1])
                self.known_peers[peer.pid] = peer
            self.logger.debug("Open cache: " + filename + " (" + str(len(self.known_peers)) + " peers)")
        c.close()


    def _update_snippets_return_pids_not_there(self, peer_list, snippet_list, default_status=None):
        """ Updates snippets with peers status and score, and
            returns a list with pids that are in the peer_list, 
            but not in the snippet_list (used in insert_reponse())
            @peer_list     a list of peers: PeerList()
            @snippet_list  a list of snippets: SnippetList()
        """
        all_peers = dict()
        to_be_inserted = dict()
        for (peer, status, score) in peer_list:
            all_peers[peer.pid] = (status, score)
            to_be_inserted[peer.pid] = (status, score) # exact copy of all_peers
        for snippet in snippet_list:
            new_origins = list()
            for (pid, status, score) in snippet.origins:
                if pid in all_peers:
                    (new_status, new_score) = all_peers[pid]
                    new_origins.append((pid, new_status, new_score)) 
                    if pid in to_be_inserted:
                        del to_be_inserted[pid]
                else:
                    new_origins.append((pid, status, score)) 
            snippet.origins = new_origins 
        return_list = list()
        for pid in to_be_inserted:
            (status, score) = to_be_inserted[pid]
            if default_status:
                status = default_status
            return_list.append((pid, status, score))
        return return_list
                

    def insert_response(self, query, peer_list, snippet_list, default_status=None):
        """ Caches a search response
            @query         original query
            @peer_list     a list of peers: PeerList()
            @snippet_list  a list of snippets: SnippetList()
        """
        query_text = query.normalized_text()
        #print "INSERT QUERY:", query_text
        c = self.cache.cursor()  
        #insert peers
        for (peer, status, score) in peer_list:
            if peer.pid is None:
                raise ValueError('No valid peer id assigned.')
            if not peer.pid in self.known_peers:     # new insert
                self.known_peers[peer.pid] = peer
                c.execute("insert into peers values(?,?)", (peer.pid, repr(peer)))
                self.cache.commit()
            elif self.known_peers[peer.pid].older_than(peer): # update
                self.known_peers[peer.pid] = peer   
                c.execute("update peers set peer=? where pid=?", (repr(peer), peer.pid))
                self.cache.commit()
        # insert snippets
        new_snippet_list = snippet_list.deepcopy() # do not change snippet_list
        to_be_inserted = self._update_snippets_return_pids_not_there(peer_list, new_snippet_list, default_status)
        if to_be_inserted: # add an empty snippet with origin_ids
            new_snippet_list.append(Snippet(origins=to_be_inserted))
        try:
            c.execute("insert into snippets values(?,?)", (query_text, repr(new_snippet_list)))  
        except sqlite3.IntegrityError:
            c.execute("update snippets set response=? where query=?", (repr(new_snippet_list), query_text))
        self.cache.commit()


    def update_response(self, query, peer_list, snippet_list, default_status=None):
        """ Caches a search response not overwriting the existing cache result
            @query         original query
            @peer_list     a list of peers: PeerList()
            @snippet_list  a list of snippets: SnippetList()
        """
        (old_peer_list, old_snippet_list) = self.response_by_query(query)
        old_peer_list.merge(peer_list)
        old_snippet_list.merge(snippet_list)
        self.insert_response(query, old_peer_list, old_snippet_list, default_status)


    def update_response_full(self, query, peer_list, snippet_list):
        """ Caches a search response for the query, and the peer list for the single terms
            @query         original query
            @peer_list     a list of peers: PeerList()
            @snippet_list  a list of snippets: SnippetList()
        """
        self.update_response(query, peer_list, snippet_list)
        self.update_response_backoff(query, peer_list)


    def update_response_backoff(self, query, peer_list):
        """ Caches a search response for the query, and the peer list for the single terms
            @query         original query
            @peer_list     a list of peers: PeerList()
        """
        new_peer_list = PeerList()
        for (peer, status, score) in peer_list: # set everything to TODO.
            new_peer_list.append(peer, 'TODO')
        query = query.normalized_text()
        parts = query.split('+')
        if len(parts) > 1:
            i = 0
            for part in parts:
                i += 1
                if i > 1 and i < len(parts):
                    self.update_response(Query({'q': "+".join(parts[:i])}), new_peer_list, SnippetList(), 'TODO') 
                self.update_response(Query({'q': part}), new_peer_list, SnippetList(), 'TODO')
  

    def response_by_query(self, query, default_status=None):
        """Returns a peer_list and snippet_list that exactly match a query from the cache
           @query    Query object
        """
        query_text = query.normalized_text()
        #print "RETRIEVE QUERY:", query_text
        peer_list = PeerList()
        snippet_list = SnippetList()
        c = self.cache.cursor()
        c.execute("select * from snippets where query=?", (query_text, ))
        for row in c:
            #print "ROW", query_text, repr(row)
            snippet_list = eval(row[1])
            for snippet in snippet_list:
                for (pid, status, score) in snippet.origins:
                    if self.known_peers.has_key(pid):
                        if default_status:    # change name to 'overwrite_status' !
                            status = default_status
                        score = len(query_text.split('+')) # query length is score (TODO: remove score from database?)
                        peer = self.known_peers[pid]
                        peer_list.merge_single(peer, status, score)                    
                    else:
                        self.logger.warning("Warning: Unknown persistent peer id '" + pid + "' in cached snippet")
                        snippet.origins.remove((pid, status, score))
            snippet_list.remove_empty_snippets() # those that have no title or location (only origins)
        return (peer_list, snippet_list)


    def response_by_query_full(self, query, default_status=None):
        """Returns a peer_list that approximately or exactly matches a query
           from the cache, and a snippet_list that matched exactly
           @query    Query object
        """
        query = query.normalized_text()
        parts = query.split('+')
        if len(parts) <= 1: # query with one term
            return self.response_by_query(Query({'q': parts[0]}), default_status)
        else:
            (peer_list, snippet_list) = self.response_by_query(Query({'q': parts[0]}), 'TODO')
        new_peer_list = None
        first_ok = peer_list
        if len(parts) == 2: # query with two terms
            (new_peer_list, useless_snippet_list) = self.response_by_query(Query({'q': parts[1]}), 'TODO')
        else: # query with more than two terms
            (new_peer_list, useless_snippet_list) = self.response_by_query_full(Query({'q': "+".join(parts[1:])}), 'TODO') # last part
            for i in range(2, len(parts)): # first part
                if new_peer_list:
                    peer_list.merge(new_peer_list)
                    (new_peer_list, useless_snippet_list) = self.response_by_query(Query({'q': "+".join(parts[:i])}),'TODO')
        snippet_list = SnippetList()
        if new_peer_list:
            peer_list.merge(new_peer_list)
            if first_ok: 
                (new_peer_list, snippet_list) = self.response_by_query(Query({'q': query}), default_status) #full query
                if new_peer_list:
                    peer_list.merge(new_peer_list)
        return (peer_list, snippet_list)


    def get_my_peer_id(self):
        """Returns the peer_id associated with this cache file"""
        (peer_list, snippet_list) = self.response_by_query(Query({'q': SNIPDEX_QUERY_MYSELF}))
        if peer_list:
            (peer, status, score) = peer_list[0]
            return peer.pid
        else:
            raise NameError("Own peer id not defined.")


    def get_all_peers_by_page(self, page):
        """Returns all peers per page, ten per page.
        """
        peer_list = PeerList()
        peer_ids = sorted(self.known_peers)
        if page < 1:
            page = 1
        first = (page - 1) * 10
        last = first + 10
        for peer_id in peer_ids[first:last]:
            peer_list.append(self.known_peers[peer_id], 'TODO', 1.0)
        return (peer_list, SnippetList())
        

class SnippetList(object):
    """A SnippetList is a ranked list of Snippet objects.

       The ranking is implicit in the ordering. The first item to be
       added is number 1 in the ranked list, et cetera.
       Alternatively results may be ordered by origin as well. For
       example: first all results from YouTube, then all results for
       FlickR, et cetera.
    """

    __slots__ = [ "snippets", "signatures", "all_origins", "ranked" ]

    def __init__(self, *args):
        self.ranked = False
        self.snippets = []
        self.signatures = dict()
        self.all_origins = dict()
        for snippet in args:
            self.append(snippet)

    def append(self, snippet):
        """Adds a new snippet to the list.
           NOTE: No duplication detection is performed.

           @param snippet The snippet to add.
        """
        self.snippets.append(snippet)
        self.signatures[snippet.get_signature()] = len(self.snippets)-1
        for (pid, status, score) in snippet.origins:
            self.all_origins[pid] = 1

    def deepcopy(self):
        """Our own deepcopy (deepcopy library gives errors)"""
        snippet_list = SnippetList()
        for snippet in self.snippets:
            snippet_list.append(snippet)
        return snippet_list


    def merge(self, other_list):
        """Merges this list with another list "round robin", but
           skips duplicates based on the signature of each snippet.

           @param other_list The other snippetlist to merge.
        """
        new_snippets = SnippetList()
        nr_merged = len(self.all_origins) 
        if nr_merged < 1:
            nr_merged = 1
        len_these_snippets = len(self.snippets) 
        len_other_snippets = len(other_list) 
        i = 0
        j = 0
        while i < len_these_snippets or j < len_other_snippets:
            if i < len_these_snippets:
                new_snippets.append(self.snippets[i])
                i += 1
            if i % nr_merged == 0 or i >= len_these_snippets:   # TODO: nr_merged instead of 2
                if j < len_other_snippets:
                    if self.signatures.has_key(other_list[j].get_signature()):
                        # signatures contains for each url (signature) the index in the original list
                        self.snippets[self.signatures[other_list[j].get_signature()]].add_origins(other_list[j].origins)
                    else:
                        new_snippets.append(other_list[j])
                    j += 1
        self.snippets    = new_snippets.snippets
        self.signatures  = new_snippets.signatures
        self.all_origins = new_snippets.all_origins

    def trim(self, count):
        """Trims the result list, so that only the first n items remain.
           NOTE: If the length of the list is already smaller, this has no effect
           TODO: now the signatures are not correct anymore?

           @count   maximum list size
        """
        self.snippets = self.snippets[:count]
                
    def remove_empty_snippets(self):
        """Removes snippets that only have origins but no title or a location"""
        new_snippet_list = SnippetList()
        for snippet in self.snippets:
            if snippet.title or snippet.location:
                new_snippet_list.append(snippet)
        self.snippets    = new_snippet_list.snippets
        self.signatures  = new_snippet_list.signatures
        self.all_origins = new_snippet_list.all_origins

    def add_origin(self, origin_id, status=None, score=1.0):
        """Adds origin_id to each snippet in the list"""
        self.all_origins[origin_id] = 1
        for snippet in self.snippets:
            snippet.add_origin(origin_id, status, score)

    def get_origin_bins(self):
        """Retrieves the snippets contained in this list binned by
           their origin. This can be used for aggregated rendering of verticals.

           This returns two data structures, the first, a dictionary contains
           for each unique origin all the associated snippets in a (smaller) SnippetList.
           The second contains scores for each origin. A higher score indicates a higher 
           importance. Scores are sorted low to high.

           @return (origin_scores: list with (origin, score) tuples, origin_items : dictionary)
        """
        origin_items = {}
        origin_scores = {}

        # Creates two dictionaries based on the origin of the snippets
        # in the list. The first list is simply a dictionary with all
        # unique origins and the results provided by that origin.
        # The second contains scores: the higher the score of an origin,
        # the more of it's results are in the top of the index.

        index = 1
        for snippet in self.snippets:
            for origin_id in snippet.origin_ids:
                origin_items.setdefault(origin_id, SnippetList()).append(snippet)
                origin_scores[origin_id] = origin_scores.setdefault(origin_id, 0.0) + 1.0/float(index)
                index += 1
        scores = sorted(origin_scores.items(), key=itemgetter(1))
        return (scores, origin_items)

    def __getitem__(self, k):
        """Retrieves a specific item.

           @param k The index (or slice) to retrieve.
        """
        return self.snippets.__getitem__(k)

    def __iter__(self):
        return self.snippets.__iter__()

    def __len__(self):
        return len(self.snippets)

    def __repr__(self):
        result = ""
        count = 0
        for snippet in self.snippets:
            if count < 250: # not more than 255 arguments in Python eval()
                count += 1           
                if result != "":
                    result += ", "
                result += repr(snippet)
        return "SnippetList(" + result + ")"


class Snippet(object):
    """Defines a snippet for a resource indexed by the search system.
    """
    __slots__  = ["origins", "location", "title", "found", 
                  "summary", "extended_summary", 
                  "type", "preview", "geolocation", 
                  "direct_links", "service_links", "attributes"]

    def __init__(self, origins, location = None, title = None, found = None, summary = None,
                 extended_summary = None, preview = None, geolocation = None,
                 direct_links = None, service_links = None, attributes = None):
        """Creates a new snippet. All parameters are in text format.

           @param origins           List of tuples (pid, status, score) of the origin(s) of the snippet. MUST be present.
           @param location          url (TODO: type, method)
           @param title             The title of the resource (recommended length: 1--80 chars), maximum: 256 chars.
           @param found             Updated datetime (optional), this should be a Python datetime.
           @param summary           Short summary (recommended length: ~180 chars), maximum: 512 chars.
           @param extended_summary  Long  summary (recommended length: ~720 chars), maximum: 2048 chars.
           @param preview           A tuple with (mime-type, location, width, height) of a renderable preview or None. 
           @param geolocation       If set, this search result is associated with the specified geolocation.
           @param direct_links      List of direct links in the page : [(description, link), ...].
           @param service_links     List of service links regarding this resource : [ (description, link), ...].
           @param attributes        Key/value pairs with further details : [(key, value), ...].
        """
        if direct_links is None: 
            direct_links = []
        if service_links is None: 
            service_links = []
        if attributes is None: 
            attributes = []
        self.location         = location
        self.title            = title
        self.found            = found
        self.summary          = summary
        self.extended_summary = extended_summary
        self.origins          = origins
        self.preview          = preview
        self.geolocation      = geolocation
        self.direct_links     = direct_links
        self.service_links    = service_links
        self.attributes       = attributes

    def add_direct_link(self, description, link):
        self.direct_links.append((description, link))

    def add_service_link(self, description, link):
        self.service_links.append((description, link))

    def add_attribute(self, key, value):
        self.attributes.append((key, value))

    def add_origin(self, origin_id, origin_status=None, origin_score=0):
        for (pid, status, score) in self.origins:
            if pid == origin_id:
                change = False
                if origin_score > score: 
                    change = True
                else:
                    origin_score = score
                if origin_status and origin_status != 'TODO' and origin_status != status:
                    change = True
                else:                    
                    origin_status = status
                if change:
                    self.origins.remove((pid, status, score))
                    self.origins.append((origin_id, origin_status, origin_score))
                break
        else:               
            self.origins.append((origin_id, origin_status, origin_score))

    def add_origins(self, new_origins):
        for (pid, status, score) in new_origins:
            self.add_origin(pid, status, score)

    def get_signature(self):
        if not self.location:  # no location, take the title 
            return self.title
        elif self.location.find("://") == -1: # location is not an absolute url
            return self.location  # TODO: see code in html.py
        else:
            location = re.sub("http://www.", "http://", self.location) # frequently used url normalizations
            location = re.sub("index.html?", "", location)  
            return location

    def __repr__(self):
        result = ""
        for attribute in Snippet.__slots__:
            value = getattr(self, attribute, "")
            if value:
                if result != "":
                    result += ","
                result += attribute + "=" + repr(value)
        return "Snippet(" + result + ")"


    def snipdex_response_snippet(self):
        """Outputs XML version of a snippet.
        """
        result = u"<snippet>\n"
        if self.origins:
            for (origin, status, score) in self.origins:
                result += "\t<origin pid=" + saxutils.quoteattr(origin) + "/>\n" 
        if self.location:
            result += "\t<location>" + saxutils.escape(self.location) + "</location>\n"
        if self.title:
            result += "\t<title>" + saxutils.escape(self.title) + "</title>\n"               
        if self.found:
            result += "\t<found>" + saxutils.escape(self.found) + "</found>\n"
        if self.summary:
            result += "\t<summary>" + saxutils.escape(self.summary) + "</summary>\n"
        if self.extended_summary:
            result += "\t<extended_summary>" + saxutils.escape(self.extended_summary) + "</extended_summary>\n"
        if self.preview:
            result += "\t<preview type=" + saxutils.quoteattr(self.preview[0])
            if not self.preview is None and len(self.preview) > 3: 
                if self.preview[2]:
                    result += " width=" + saxutils.quoteattr(str(self.preview[2]))
                if self.preview[3]:
                    result += " height=" + saxutils.quoteattr(str(self.preview[3]))
            result +=">" + saxutils.escape(self.preview[1]) + "</preview>\n"

        # Links and Attributes
        if len(self.direct_links) > 0 or len(self.service_links) > 0:
            result += "\t<links>\n"
            for description, link in self.direct_links:
                result += "\t\t<link type='direct' description=" + saxutils.quoteattr(description) + ">" + saxutils.escape(link) + "</link>\n"
            for description, link in self.service_links:
                result += "\t\t<link type='service' description=" + saxutils.quoteattr(description) + ">" + saxutils.escape(link) + "</link>\n"
            result += "\t</links>\n"
        if len(self.attributes) > 0:
            result += "\t<attributes>\n"
            for key, value in self.attributes:
                result += "\t\t<attribute key=" + saxutils.quoteattr(key) + " value=" + saxutils.quoteattr(value) + " />\n"
            result += "\t</attributes>\n"

        result += "</snippet>\n"
        return result


class PeerList(object):
    """A PeerList is a ranked list of Snippet objects.
    """
    __slots__ = [ "peers", "pids" ]  # TODO: pids

    def __init__(self, *args):
        self.peers = []
        for row in args:
            self.append(row)

    def append(self, peer, status='DONE', score=None):
        """Adds a new peer to the list.
           NOTE: No duplication detection is performed.
           @param peer The snippet to add.
        """
        self.peers.append((peer, status, score))

    def merge_single(self, new_peer, new_status='DONE', new_score=1.0):
        """Adds a new peer to the list if not already present.
           A score never gets lower.
           The status never returns to 'TODO'
           @param peer The peer to add.
        """
        new_peer_list = PeerList()
        found = False
        for (peer, status, score) in self.peers:
            if peer.pid == new_peer.pid:
                found = True
                if peer.older_than(new_peer):
                    peer = new_peer
                if score < new_score:
                    score = new_score
                if status == 'TODO' and new_status != 'TODO':
                   status = new_status
            new_peer_list.append(peer, status, score)
        if not found:
            new_peer_list.append(new_peer, new_status, new_score)
        self.peers = new_peer_list.peers
            

    def merge(self, peer_list):
        """Adds new peers to the list if not already present.
           @param peer_list The peers to add.
           TODO: this can be done more efficiently!
        """
        for (peer, status, score) in peer_list:
            self.merge_single(peer, status, score)

    def __getitem__(self, k):
        """Retrieves a specific item.
           @param k The index (or slice) to retrieve.
        """
        return self.peers.__getitem__(k)

    def __iter__(self):
        return self.peers.__iter__()

    def __len__(self):
        return len(self.peers)

    def __repr__(self): 
        """Representation of peer_list does not show status and score"""
        result = ""
        count = 0
        for (peer, status, score) in self.peers:
            if count < 250: # not more than 255 arguments in Python eval()
                count += 1
                if result != "":
                    result += ", "
                result += repr(peer)
        return "PeerList(" + result + ")"


class Peer(object):
    __slots__ = ["pid", "name", "description", "icon", "language", 
                 "adult_content", "hashtag", "query_hints", "updated",
                 "open_template", "html_template", "suggest_template", 
                 "public_address", "local_address"]

    def __init__(self, pid=None, name=None, description=None, icon=None, language=None, 
                 adult_content=False, hashtag=None, query_hints=None, updated=None,
                 open_template=None, html_template=None, suggest_template=None, 
                 public_address=None, local_address=None):
        """ Creates a new peer. All parameters are in text format unless stated otherwise
            Real peers must have pid. Zombi peers must have open_template (used to determine the pid)

            @pid                 persistent peer id
            @name                peer name
            @description         peer description
            @icon                peer's favicon
            @language            peer language (RFC 3066)
            @adult_content       (boolean): not to be queried in safe search mode
            @hashtag             single hashtag, such as "#videos" or "#books"
            @query_hints         list of query_hints, to trigger peer. 
                                 Hints will be removed from the query
            @updated             Updated datetime (optional), this should be a Python datetime.
            @open_template       tuple consisting of (url template, mimetype, method, and XPath query
                                 strings for scraping: result, title, url, description, preview, attributes)
            @html_template       See open_template, but mimetype must be "text/html"
            @suggest_template    tuple consisting of (url template, mimetype)
            @public_address      public address: sever string, e.g. "130.89.11.159:8472"
            @local_address       local address behind NAT box 
        """      
        self.pid                 = pid
        self.name                = name
        self.description         = description
        self.icon                = icon
        self.language            = language
        self.adult_content       = adult_content
        self.hashtag             = hashtag
        self.query_hints         = query_hints
        self.updated             = updated
        self.open_template       = open_template
        self.html_template       = html_template
        self.suggest_template    = suggest_template
        self.public_address      = public_address
        self.local_address       = local_address
        if self.pid is None:
            self.pid = self.get_peer_id()
     
    def get_peer_id(self):
        if self.pid:
            return self.pid
        if self.open_template:
            template = self.open_template[0]
        elif self.html_template:
            template = self.html_template[0]
        else:
            template = None
        if template:
            return hashlib.md5(template).hexdigest()
        else:
            return None

    def set_peer_id(self, pid):
        if self.pid:
            raise ValueError('Peer id cannot be overridden.')
        else:
           self.pid = pid

    def set_updated_to_now(self):
        self.updated = right_now()

    def get_open_template(self):
        """ Provides an OpenSearch template, either from the explicit attribute, 
            or from the ip and port number of the Snipdex Peer
        """
        if self.public_address: 
            return ("http://" + self.public_address +
                    "/snipdex/?q={q}&h={h?}&p={p?}&l={l?}&f=xml&v=" +
                    SNIPDEX_RESPONSE_VERSION, "application/snipdex+xml")
        elif self.open_template:
            return self.open_template
        elif self.html_template and len(self.html_template) > 3: 
            return self.html_template
        else:
            raise ValueError("no open access to peer: " + repr(self.pid))

    def older_than(self, peer):
        """ See if peer was updated later than self, and has a new ip address (or name).
            If so, return Tue.
        """
        if peer.updated and (not self.updated or self.updated < peer.updated):
            return True
        else:
            return False
                      
    def __repr__(self):
        result = ""
        for attribute in Peer.__slots__:
            value = getattr(self, attribute, "")
            if value:
                if result != "":
                    result += ","
                result += attribute + "=" + repr(value)
        return "Peer(" + result + ")"


    def snipdex_response_peer(self, status='DONE', score=1):
        """Outputs XML version of a snippet.
        """
        result = u"<peer pid=" + saxutils.quoteattr(self.pid) 
        result += " status=" + saxutils.quoteattr(status) 
        if score is not None:
            result += " score=" + saxutils.quoteattr(str(score))
        result += ">\n"
        if self.name:
            result += "\t<name>" + saxutils.escape(self.name) + "</name>\n"
        if self.description:
            result += "\t<description>" + saxutils.escape(self.description) + "</description>\n"
        if self.icon:
            result += "\t<icon>" + saxutils.escape(self.icon) + "</icon>\n"
        if self.language:
            result += "\t<language>" + saxutils.escape(self.language) + "</language>\n"
        if self.adult_content:
            result += "\t<adult_content>True</adult_content>\n"
        if self.query_hints:
            for hint in self.query_hints:
                result += "\t<query_hint>" + saxutils.escape(hint) + "</query_hint>\n"
        if self.updated:
            result += "\t<updated>" + saxutils.escape(self.updated) + "</updated>\n"
        result += self.snipdex_response_template(self.open_template, "open_template")
        result += self.snipdex_response_template(self.html_template, "html_template")
        result += self.snipdex_response_template(self.suggest_template, "suggest_template")
        if self.public_address:
            result += "\t<public_address>" + saxutils.escape(self.public_address) + "</public_address>\n"
        if self.local_address:
            result += "\t<local_address>" + saxutils.escape(self.local_address) + "</local_address>\n"
        result += "</peer>\n"
        return result


    def snipdex_response_template(self, template, tag):
        """ XML format of template """
        result = ""
        if template:
            result += "\t<" + tag
            nr = 1
            for attr in ("type", "method", "item_path", "title_path", "link_path", "summary_path", "preview_path", "attribute_paths"):
                if len(template) > nr and template[nr]: 
                    result += " " + attr + "=" + saxutils.quoteattr(template[nr])
                nr += 1
            result += ">" + saxutils.escape(template[0]) + "</" + tag + ">\n"
        return result



class Query(object):
    __slots__ = ["query_param"]

    def __init__(self, query_param=None):
        self.query_param = dict()
        if query_param:
            for key in query_param:
                self.query_param[key] = query_param[key]

    def fill_template_url(self, url, normalize=True):
        """Puts the query in the urlTemplate HTTP GET url.
    
           @return HTTP Get string representation of this Query object.
        """
        url = url.replace("&amp;", "&")
        for key in self.query_param:
            if normalize and key == 'q':
                value = self.normalized_text()
            else:
                value = self.query_param[key]
            url = re.sub("{" + key + "\??}", value, url) 
        url = re.sub("\{[^\}\?]*\?\}", "", url)
        return url

    def unicode_text_from_query(self):
        if 'q' in self.query_param:
            return urllib.unquote_plus(self.query_param['q']).decode('utf-8', 'ignore')
        else:
            return ''

    def normalized_text(self):
        """ Gives a normalized representation used internally for searching. 
            The internal representation can include one hashtag term, which
            is put in front of the query, e.g. '#videos'.
            Hash tags may be given by the 'h' paramenter
        """ 
        if 'q' in self.query_param:
            text = urllib.unquote_plus(self.query_param['q']) 
        else:
            text = ''
        if 'h' in self.query_param:
            tag = urllib.unquote_plus(self.query_param['h'])
            if tag:
                if tag[0] != '#':
                    tag = '#' + tag
                tag = re.sub("\s+", "", tag) #no spaced allowed in tag
        else:
            tag = ''
        text = re.sub("\s+", " ", text)
        text = re.sub("^ ", "", text)
        text = re.sub(" $", "", text)
        if text:
            terms = text.split(' ')
            text = ''
            for term in terms:
                if term[0] == '#':
                    if tag:
                       term = term[1:]
                    else:
                        tag = term
                        term = ''
                if text and term:
                    text = text + ' ' + term
                elif term: 
                    text = term  
        if text and tag:
            text = tag + ' ' + text
        elif tag:
            text = tag
        return urllib.quote_plus(text.lower())

    def length(self): 
        query_text = self.normalized_text()
        return len(query_text.split('+'))

    def add_key_value(self, key, value):
        self.query_param[key] = value

    def add_query(self, query):
        if query.query_param:
            for key in query.query_param:
                self.query_param[key] = query.query_param[key]

    def get(self, key, default=None):
        return self.query_param.get(key, default)

    def __getitem__(self, key):
        return self.query_param.__getitem__(key)

    def __setitem__(self, key, value):
        return self.query_param.__setitem__(key, value)

    def __iter__(self):
        return self.query_param.__iter__()

    def __len__(self):
        return len(self.query_param)

    def __repr__(self):
        result = ""
        if self.query_param:
            for key in self.query_param:
                if result != "":
                    result += ","
                result += str(key) + ":" + repr(self.query_param[key])
        return "Query({" + result + "})"



# Testing...
if (__name__ == '__main__'): 
    import logging
    logger = logging.getLogger("SnipdexData")
    logging.basicConfig(level=logging.DEBUG, format="%(name)-11s %(message)s")
    logger.debug("Testing. " + right_now())

    # Open cache
    cache = SnipdexCache('/tmp/snipdex-cache-127-0-0-1_8472', logger)

    # Create a peer list and add a peer
    peer_list = PeerList()
    pid = cache.get_my_peer_id()
    peer = Peer(pid=pid, public_address='127.0.0.1', updated="2011-07-22 12:00")
    peer_list.append(peer)
    logger.debug("Template: " + str(peer.get_open_template()))
    logger.debug("Old: " + repr(peer_list))

    # Create a snippet list and add a snippet (creates a warning: we refer to non-existing peer!)
    snippet_list = SnippetList()
    snippet = Snippet(title="SnipDex", 
                      summary='"Samen het web doorzoeken"', 
                      origins=[('DoEsNoteXiST', 'TODO', None)], #origins=[(cache.get_my_peer_id(), "DONE", 1.0)]
                      location='http://www.snipdex.net/',
                      preview=('image/jpg', 'http://www.snipdex.net/snipdex_logo.jpg', '485', '180'),
                      attributes=[('Button', 'Zoek'), ('About', 'Over')],   
                      )
    snippet_list.append(snippet) 
    snippet = Snippet(location="http://www.utwente.nl", title="Universiteit Twente", 
                         summary="De ondernemende universiteit", 
                         origins=[],
                         attributes=[('Rating', '10'), ('Number of students', '7000')],
                         preview=('image/jpg', 'http://www.utwente.nl/media/580789/banner_218x128.jpg'))
    snippet_list.append(snippet)
    snippet_list.add_origin(pid, 'DONE')
    logger.debug(repr(snippet_list))
 
    peer = Peer(pid=pid, public_address='127.0.0.2', name='BOOOO', updated="2012-01-01 12:00")
    peer_list.merge_single(peer)


    # Cache the peers and snippets
    cache.update_response_full(Query({'q': "snipdexiamback"}), peer_list, snippet_list)

    # Create a peer list and add a peer
    
    peer_list = PeerList()
    peer = Peer(name="Djoerd Hiemstra",
                description="A bit of teaching, some research, shake well...",
                icon="http://wwwhome.cs.utwente.nl/~hiemstra/images/tux.ico",
                open_template=("http://wwwhome.cs.utwente.nl/~hiemstra/?os={q}", "application/rss+xml"),
                html_template=("http://wwwhome.cs.utwente.nl/~hiemstra/?s={q}", "text/html"))
    peer_list.append(peer, 'DONE', 1.0)   # We set it to 'DONE' while it will not be...
    logger.debug("Template 2: " + str(peer.get_open_template()))

    # Cache the peers for a query (empty snippet list)
    cache.update_response_full(Query({'q': "djoerd+hiemstra"}), peer_list, SnippetList())
    
    logger.debug("Old 2:" + repr(peer_list))
    logger.debug("I am " + repr(pid))

    # See what comes back 
    (new_peer_list, new_snippet_list) = cache.response_by_query_full(Query({'q': "muis"}))

    for (peer, status, score) in new_peer_list:
        logger.debug("(" + repr(peer) + ", " + repr(status) + ", " + repr(score) + ")")

    #new_snippet_list.merge(snippet_list) # now the non-existing peer should be there again.
    logger.debug("New " + repr(new_snippet_list))

