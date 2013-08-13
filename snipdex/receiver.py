#!/usr/bin/env python
"""
receiver.py: Snipdex Peer HTTP Request Receiver

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

import os
import urlparse 
import socket
import BaseHTTPServer
import time

from threading import Thread
from string import Template

# local imports
import snipdata
import sender
import html

class PeerRequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    """Handles HTTP peer requests of the following form:
       http://127.0.0.1:8472/snipdex/xxx.yyy
       http://127.0.0.1:8472/snipdex/?q={q}&h={h}&p={p}&l={l}&f={f}&v={v}
         q= query_text
         p= page (default is 1)
         h= hashtag (vertical)
         l= language (default is taken from http headers)
         f= format: must be one of ['html', 'xml'] (default is 'html')
         v= version: Snipdex version number (default = current_version)
       http://127.0.0.1:8472/snipdex/pitch (HTTP POST)
         format to be decided
    """
    command_handler = None  # Will be set in main.py, see class PeerCommandHandler below

    def do_GET(self):
        """ Overrides the standard method of the BaseHTTPRequestHandler
            It performs a search, or it gets files from the local web directory
        """
        parsed_path = urlparse.urlparse(self.path)
        local_path  = parsed_path.path
        query       = parsed_path.query 
        date        = None
        mimetype    = 'text/html'

        try:
            param = snipdata.Query(dict([part.split('=') for part in query.split('&')]))
        except:
            param = snipdata.Query()
        param.add_key_value('public_ip', str(self.client_address[0]))  # add the clients ip
        param.add_key_value('public_port', str(self.client_address[1]))
        headers = None  # self.my_headers()

        # Possible TODO: html access only allowed for localhost?
        if local_path == "/" or local_path == "/snipdex":  # Moved permanently
            self.send_response(301)  
            self.send_header("Location", "/snipdex/")
            self.end_headers()
            return
        query_text = param.normalized_text()
        if (local_path == "/snipdex/" or local_path == "/snipdex/index.html") and query_text != u'':
            if (query_text == snipdata.SNIPDEX_QUERY_PONG): 
                # exchange greetings
                (peer_list, snippet_list) = self.command_handler.get_all_peers(param)
            else:
                # perform a search            
                (peer_list, snippet_list) = self.command_handler.search(param, headers)
            if 'f' in param and param['f'] == 'xml':
                result = snipdata.snipdex_response(param, peer_list, snippet_list) # output XML
                mimetype = 'text/xml'
            else: 
                result = self.command_handler.snipdex_render(param, peer_list, snippet_list)  # output HTML
            result = result.encode('utf-8', 'ignore')
        else:
            try:
                (result, mimetype, date) = self.command_handler.get_file(local_path)                 
            except IOError:
                self.send_error(404, "Snipdex Not Found: " + local_path)
                return
        self.send_response(200)
        self.send_header("Content-type", mimetype)
        self.send_header("Content-Length", str(len(result)))
        self.send_header("Last-Modified", self.date_time_string(date))
        self.end_headers()
        self.wfile.write(result) 


    def do_POST(self):
        """ Overrides the standard method of the BaseHTTPRequestHandler"""
        pass #TODO: pitch


    def my_headers(self):
        """ Returns a dict with header information"""
        dict_headers = dict()
        for item in self.headers.headers:
            (key, sep, value) = item.partition(": ")
            if key in ['User-Agent']:  # ['Accept', 'Accept-Charset', 'Accept-Encoding', 'Accept-Language', 'If-Modified-Since', 'User-Agent']:
                value.replace('\r\n', '')
                dict_headers[key] = value
        return dict_headers


class PeerCommandHandler(object):
    """Represents a search peer in the network.
    """
    __slots__ = ["my_pid", "my_updated", "local_ip", "local_port", "public_ip", "public_port",
                 "mother_peer", "original_mother_address", "webroot", "cache", "fall_back_peer_list",
                 "logger", "overlay", "result_template", 
                 "trademark", "motto", "logo", "button"]

    def __init__(self, my_port, mother_ip, mother_port, webroot, cachefile, logger):
        """Creates a new Search Peer.

        @param port The port used by this peer.
        @param mother_ip The IP to use to communicate with the Mother Peer.
        @param mother_port The port to use to communicate with the Mother Peer.
        @param web_location Location of the web data.
        @param logger Logging object to be used.
        """
        # defaults may be overridden after registration at mother
        self.trademark       = "SnipDex"
        self.motto           = '"Search the Web Together"'
        self.logo            = ('image/png', 'snipdex_logo.png', 485, 180) 
        self.button          = 'Search'
        self.local_port      = my_port
        self.webroot         = webroot
        self.logger          = logger
        self.cache           = snipdata.SnipdexCache(cachefile, logger)
        self.my_pid          = self.cache.get_my_peer_id()
        self.overlay         = self.init_overlay(webroot)
        f = open(webroot + "/results.html", "r")
        self.result_template = f.read()
        f.close()
        self.original_mother_address = mother_ip + ":" + str(mother_port)
        if mother_ip != '127.0.0.1' or mother_port != my_port:
            (self.mother_peer, self.fall_back_peer_list) = self._register(mother_ip, mother_port)
        else:
            self.ip_without_register()                
            self.mother_peer = None
            self.fall_back_peer_list = None
            self.logger.warning("Warning: Mother peer and peer are equal; in stand-alone mode.")


    def ip_without_register(self):
        """Get ip and port by pinging snipdex.net
        """
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('www.utwente.nl', 80))                          # TODO?: Py2.7 create_connection()
        (local_ip, local_port) = s.getsockname()                    #(peer_ip, peer_port)  = s.getpeername() 
        self.store_ips(local_ip, local_port, local_ip, local_port)  # Assume we're not behin a NAT box

        
    def store_ips(self, public_ip, public_port, local_ip, local_port): 
        """Store our public_ip number. Stuff with ports is currently not used.
        """
        self.public_ip = public_ip
        self.local_ip = local_ip
        if local_ip == self.public_ip: 
            self.public_port = self.local_port
        else:
            self.public_port = public_port


    def store_search_engine_details(self, snippet):
        """Store snippet details to adjust user interface
        """
        if snippet.title:
            self.trademark = snippet.title
        if snippet.preview:
            self.logo = snippet.preview
            if len(self.logo) < 3: 
                self.logo = (self.logo[0], self.logo[1], "485", "180")  # add default size
        if snippet.summary:
            self.motto = snippet.summary
        for (key, value) in snippet.attributes:
            if key == 'Button':
                self.button = value


    def ips_from_query_param(self, query_param):
        """Get the ips and ports from the query_parameters
        """
        public_ip   = query_param.get('public_ip')
        public_port = query_param.get('public_port')
        local_ip    = query_param.get('local_ip')
        local_port  = query_param.get('local_port')
        peer_ip     = query_param.get('peer_ip')
        peer_port   = query_param.get('peer_port')
        return (public_ip, public_port, local_ip, local_port, peer_ip, peer_port)


    def _register(self, mother_ip, mother_port):
        """Registers peer at the mother peer
        """
        mother_address = mother_ip + ":" + str(mother_port)
        new_mother_address = None
        mother_peer = snipdata.Peer(public_address=mother_address)
        peer_link = sender.PeerLink(mother_peer.get_open_template(), self.logger)
        query = snipdata.Query({'q': snipdata.SNIPDEX_QUERY_REGISTER})
        try:
            (new_query, peer_list, snippet_list, total_results) = peer_link.search(query)
        except IOError:
            (peer_list, snippet_list) = self.cache.response_by_query(query)  
            self.ip_without_register()
            if peer_list and snippet_list:
                (peer, status, score) = peer_list[0] # The first result is the mother
                new_mother_address = peer.public_address
                self.logger.warning('Warning: Connection to mother peer failed. Using old settings.')
            else:
                raise IOError('Connection to mother peer failed.') 
        else:
            (public_ip, public_port, local_ip, local_port, peer_ip, peer_port) = self.ips_from_query_param(new_query)
            if not public_ip:
                raise IOError('Public ip number cannot be determined.')     
            new_mother_address = peer_ip + ":" + str(mother_port)
            self.store_ips(public_ip, public_port, local_ip, local_port)
            
            # Logging...
            self.logger.debug("Succesfully registered at mother peer " + mother_address)
            if mother_address != new_mother_address:
                self.logger.debug("Peer's public address: " + new_mother_address)
            self.logger.debug("Your public addresses: " + self.public_ip + ":" + str(self.public_port))
            if self.local_ip != self.public_ip:
                self.logger.debug("Your local Address: " + self.local_ip + ":" + str(self.local_port))

        if peer_list:
            (peer, status, score) = peer_list[0] # The first result might be the peer itself
            if status == 'ME' and (peer.public_address == mother_address 
                or peer.public_address == new_mother_address or peer.local_address == new_mother_address):
                mother_peer = peer
            else:            
                raise IOError('No pid for mother peer.')
            if len(peer_list) > 1:
                fall_back_peer_list = peer_list[1:] # The others are default peers
            else:
                fall_back_peer_list = snipdata.PeerList()
        else:
            raise IOError('No information for mother peer.')
        if snippet_list:
            engine_snippet = snippet_list[0]
            self.store_search_engine_details(engine_snippet) # The first result is used to override UI defaults
            if engine_snippet.title or len(peer_list) > 1:   # TODO: Instead, maybe location MUST be snipdex.org, and use cache_update(?)
                self.cache.insert_response(query, peer_list, snippet_list) #overwrite old
        else:
            raise IOError('Connection to p2p network failed.')
        return (mother_peer, fall_back_peer_list)


    def init_overlay(self, webroot):
        """Initializes the virtual web directory overlay.

           This creates a mapping from the virtual directory (on http://localhost:port/)
           to actual files on the disk which may be arranged differently. 

           @param webroot The root where the actual files are located.
        """
        overlay = dict()
        overlay["/snipdex/"]           = ("text/html", webroot + "/index.html")
        overlay["/snipdex/index.html"] = ("text/html", webroot + "/index.html")
        overlay["/snipdex/about.html"] = ("text/html", webroot + "/about.html")
        overlay["/snipdex/snipdex.osdx"] = ("application/opensearchdescription+xml", webroot + "/snipdex.osdx")
        overlay["/snipdex/geolocation.js"] = ("text/javascript", webroot + "/geolocation.js")
        overlay["/snipdex/snipdex_logo.png"] = ("image/png", webroot + "/snipdex_logo.png")
        overlay["/snipdex/snipdex_logo_small.png"] = ("image/png", webroot + "/snipdex_logo_small.png")
        overlay["/favicon.ico"] = ("image/vnd.microsoft.icon", webroot + "/favicon.ico")
        overlay["/snipdex/favicon.ico"] = ("image/vnd.microsoft.icon", webroot + "/favicon.ico")
        overlay["/snipdex/clover.b64"] = ("multipart/mixed", webroot + "/clover.b64")
        return overlay

                
    def get_file(self, location_path):
        """Send a file, which resides on disk, back to the requester.

           @param location_path Value of http get.
        """
        if location_path in self.overlay:
            (mimetype, path) = self.overlay[location_path]               
            if mimetype.startswith("text/") or mimetype.endswith("+xml"): # Open the file in the right mode
                mode = "r"
            else:
                mode = "rb"
            f = open(path, mode)
            fs = os.fstat(f.fileno())
            date = fs.st_mtime
            contents = f.read()
            f.close()
            if mode == "r":
                template = Template(contents)
                contents = template.substitute(trademark=self.trademark, motto=self.motto, 
                               logo=self.logo[1], logo_width=self.logo[2], logo_height=self.logo[3], 
                               button=self.button, port=str(self.local_port))
                contents = contents.decode('utf-8', 'ignore')
            return (contents, mimetype, date)
        else:
            raise IOError


    def put_myself_first(self, peer_list):
        """Add myself as the first peer"""
        pid = self.cache.get_my_peer_id()
        my_public_address = self.public_ip + ":" + str(self.public_port)
        if self.local_ip != self.public_ip:
            my_local_address = self.local_ip + ":" + str(self.local_port)
        else:
            my_local_address = None
        me = snipdata.Peer(pid=pid, public_address=my_public_address, local_address=my_local_address)
        me.set_updated_to_now()
        peer_list_new = snipdata.PeerList()
        peer_list_new.append(me, 'ME', None) # the real 'ME'
        peer_list_new.merge(peer_list)
        return peer_list_new


    def get_all_peers(self, query):
        """Returns all peers per page, ten per page.
           Only the mother peer will receive these, if the query SNIPDEX_QUERY_PONG
           is issued. This way, the mother knows the peer is availble for search.
           The peers can be used by the mother to initiate query-based sampling.
        """
        public_ip = query['public_ip']
        (mother_ip, mother_port) = self.mother_peer.public_address.split(':',1)
        try:
            page = int(query['p'])
        except (KeyError, ValueError):
            page = 1
        if public_ip == mother_ip and query.normalized_text() == snipdata.SNIPDEX_QUERY_PONG: # 2nd check is also done above (won't hurt here)
            self.logger.debug("Contacted by Mother.")
            (peer_list, snippet_list) = self.cache.get_all_peers_by_page(page)
        else:
            (peer_list, snippet_list) = (snipdata.PeerList(), snipdata.SnippetList())        
        if page <= 1:
            peer_list = self.put_myself_first(peer_list)         
        return (peer_list, snippet_list)


    def search(self, query, headers=None): 
        """Search for a particular query. 
           If the search is done from outside, only provide cached results. 
           If the search is done from localhost, then contact peers to 
           get up-to-date search results.           

           @param query     The query to process (http query parameters)
           @return          A tuple (peer_list, snippet_list)
        """
        self.logger.debug("Processing Query : " + repr(query))

        # Try the local cache
        (peer_list, snippet_list) = self.cache.response_by_query_full(query)
        self.logger.debug("Cache: " + str(len(peer_list)) + " peers, " + 
                     str(len(snippet_list)) + " results.")

        if query['public_ip'] == '127.0.0.1':   # only do your very best for localhost :-)

            if self.mother_peer:
                peer_list.merge_single(self.mother_peer, 'TODO') # if mother already in as 'DONE' then this will change nothing.

            for time_to_life in range(3): # time to life is 2
                next_peer_list = snipdata.PeerList()
                thread_list = []
                for (the_peer, status, score) in peer_list:
                    if status == 'TODO':  # only peers who's status is 'TODO' will be contacted
                        try:
                            peer_link = sender.PeerLink(the_peer.get_open_template(), self.logger)
                        except ValueError as ex: 
                            self.logger.warning('Warning: ' + repr(ex))
                            next_peer_list.merge_single(the_peer, 'ERROR', score)
                        else:
                            altered_query = self.remove_query_hints(query, the_peer.query_hints)
                            threaded_peer = PeerSearchThread(the_peer, peer_link, altered_query)
                            thread_list.append(threaded_peer)
                            threaded_peer.start()
                    else:
                        if status == 'ME': # someone else's 'ME', the real me is added below.
                            status = 'DONE'
                        next_peer_list.merge_single(the_peer, status, score)

                start = time.time()
                for thread in thread_list:
                    while thread.status is None and time.time() - start < 4:   # block for 3 seconds max. on each hop
                        pass
                    if thread.status == 'ERROR':
                        self.logger.debug("ERROR: " + thread.peer.pid)
                        next_peer_list.merge_single(thread.peer, 'ERROR', None) # change 'TODO' to 'ERROR'
                    elif thread.status is None or thread.status == 'TIMEOUT':
                        self.logger.debug("TIMEOUT: " + thread.peer.pid)
                        next_peer_list.merge_single(thread.peer, 'TIMEOUT', None)
                    else:
                        nr_of_peers = 0
                        nr_of_snippets = 0
                        if thread.peer_list: 
                            next_peer_list.merge(thread.peer_list)
                            nr_of_peers = len(thread.peer_list)
                        if thread.snippet_list:
                            thread.snippet_list.add_origin(thread.peer.pid)
                            snippet_list.merge(thread.snippet_list)
                            nr_of_snippets = len(thread.snippet_list)
                        if thread.peer_list or thread.snippet_list:
                            next_peer_list.merge_single(thread.peer, 'DONE')
                            #self.cache.thumbs_up_for_peer(thread.peer)   maybe here gather statistics about peers?
                        else:
                            next_peer_list.merge_single(thread.peer, 'EMPTY', 0.1)  
                        
                        self.logger.debug("HTTP Response: " + thread.peer.pid + ", " 
                                          + str(nr_of_peers) + " peers, " 
                                          + str(nr_of_snippets) + " results, " 
                                          + "#hops: " + str(time_to_life + 1) + ")")
                        if thread.new_query:  # Did my ip number change?
                            (public_ip, public_port, local_ip, local_port, peer_ip, 
                                peer_port) = self.ips_from_query_param(thread.new_query) # Some of this code is also in register
                            if public_ip and public_ip != self.public_ip:
                                self.logger.debug("Your ip numbers changed from " + 
                                                     str(self.public_ip) + " to " + str(public_ip))
                                self.store_ips(public_ip, public_port, local_ip, local_port)

                if self.fall_back_peer_list:    # add fall_back peers (or default peers)
                    next_peer_list.merge(self.fall_back_peer_list)
                peer_list = next_peer_list

            self.cache.update_response_full(query, peer_list, snippet_list) 
        else:
            self.cache.update_response_backoff(query, peer_list) # we still might learn from new terms and term combinations 
            if len(peer_list) < 1 and self.fall_back_peer_list:  # add fall_back peers (or default peers)
                peer_list.merge(self.fall_back_peer_list)

        peer_list_new = self.put_myself_first(peer_list)         #  the real 'ME'
        return (peer_list_new, snippet_list)


    def remove_query_hints(self, query, query_hints):
        altered_query = snipdata.Query()
        for key in query:
            if key == 'q' and query_hints:
                value = query[key]
                for hint in query_hints:
                    value = value.replace(hint, '')
                if value:
                    altered_query.add_key_value(key, value)
                else:
                    altered_query.add_key_value(key, query[key])
            else:
                altered_query.add_key_value(key, query[key])
        return altered_query


    def snipdex_render(self, query, peer_list, snippet_list):
        """Outputs HTML version of the search results
        """
        template = Template(self.result_template)
        query_text = query.unicode_text_from_query()   #UNICODE HACK?
        results_html = html.basic_render(query, peer_list, snippet_list)
        final_html = template.substitute(query=query_text, content=results_html, 
                                         trademark=self.trademark, motto=self.motto,
                                         logo=self.logo[1], button=self.button)
        return final_html



class PeerSearchThread(Thread):
    """ Executes searches on remote peers in parallel
    """
    def __init__ (self, peer, peer_link, query):
        Thread.__init__(self)
        self.peer         = peer
        self.peer_link    = peer_link
        self.query        = query
        self.peer_list    = None
        self.snippet_list = None
        self.status       = None
        self.new_query    = None

    def run(self):
        try:
            (self.new_query, self.peer_list, self.snippet_list, total_results) = self.peer_link.search(self.query)
        except sender.httplib.socket.timeout:
            self.status = 'TIMEOUT'
        except:  # Catch all (NB 'as ex' and printing the actual error does not seem to be thread safe??)  
            self.status = 'ERROR' 
        else:
            if self.peer_list or self.snippet_list:
                self.status = 'DONE'
	            # score snippets and take the top 10 (now still without scoring)
                if self.snippet_list:
                     self.snippet_list.trim(10)
                # remove adult content
        	    # any other pre-processing step
            else:
                self.status = 'EMPTY'
            

# Testing...
#
# When initiating the PeerCommandHandler, we
#  1. open the cache.
#     a) the cache file determines our peer identifier, 
#        removing the cache means we will get a new id next time
#     b) determine our local ip by sending a upd packet to the mother peer or to snipdex.net:80
#        maybe this should be moved to the sender module, as that already makes connections.
#        (can i determine my own -local- ip with httplib? With: response.fp._sock.getpeername() and getsockname()
#     c) register at the mother peer (unless mother peer is set to localhost)
#  2. The PeerRequestHandler serves requests forever
#  3. For every request, we should update our public_ip and local_ip, but we do not for now.
#       

if (__name__ == '__main__'): 
    import logging, sys, BaseHTTPServer
    logger = logging.getLogger("SnipdexReceiver")
    logging.basicConfig(level=logging.DEBUG, format="%(name)-15s %(message)s")

    my_port = 8472
    webroot = 'web'.join(sys.path[0].rsplit('snipdex', 1))
    cachefile = '/tmp/snipdex-cache-127-0-0-1_8472'
    command_handler = PeerCommandHandler(my_port, 'stable.cs.utwente.nl', 8472, webroot, cachefile, logger)
    PeerRequestHandler.command_handler = command_handler

    logger.debug("Testing at: http://localhost:" + str(my_port) + "/snipdex/")
    server = BaseHTTPServer.HTTPServer(('', my_port), PeerRequestHandler)
    server.serve_forever()


