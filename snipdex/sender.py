#!/usr/bin/env python
"""
sender.py: Snipdex Peer HTTP Request Sender

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

import libxml2
import json
import re
import httplib

# local import
import snipdata

# libxml2 options
libxml2.registerErrorHandler(lambda *args: None, None)
HTML_PARSE_OPTIONS = libxml2.HTML_PARSE_RECOVER + libxml2.HTML_PARSE_NOERROR + libxml2.HTML_PARSE_NOWARNING
XML_PARSE_OPTIONS  = libxml2.XML_PARSE_RECOVER + libxml2.XML_PARSE_NSCLEAN

# supported formats
FORMAT_RSS         = ("//item", "title", "link", "description", ".//media:thumbnail", "Date{pubDate}", None)
FORMAT_ATOM        = ("//entry", "title", "link", "summary", ".//media:thumbnail", "Date{updated}", None)
FORMAT_XMLSUGGEST  = ("//Item", "Text", "Url", "Description", "Image", None, None)
FORMAT_HTML        = (None, "(.//a)[1]", "(.//a)[1]/@href", None, None, None, None)
FORMAT_JSONSUGGEST = ("$.*[1]", "@", None, None, None, None, None)  #jsonpath
FORMAT_NONE        = (None, None, None, None, None, None, None)  

# default headers

SNIPDEX_DEFAULT_HEADERS = ['Connection: close\r\n', 'User-Agent: SnipDex/0.2 (+http://www.snipdex.net/)\r\n','Accept-Encoding: identity\r\n', 'Accept-Charset: UTF-8;q=0.7,*;q=0.7\r\n', 'Cache-Control: no-cache\r\n', 'Accept-Language: nl,en;q=0.7,en-us;q=0.3\r\n', 'Referer: http://www.snipdex.net/\r\n']

#utility

def bound_text_no_markup(s, limit):
    """Bounds the length of s to a specific limit.
       If the length of the text exceeds the limit it is augmented
       with a ' ...' continuation marker at the end.
       if None is passed as string, this function return None as well.

       @param s The string to bound (or None).
       @return A (possibly) bounded version of the string.
    """
    if s is None:
        return None
    s = re.sub("<[^>]+>|\s+", " ", s)          # remove markup and spurious spaces
    if len(s) > limit:
        return s[:limit - 3] + "..."
    elif s == ' ':
        return None
    else:
        return s


class PeerLink(object):
    """ Link to a (real or zombi) peer.
    """
    __slots__ = [ "search_link", "mimetype", "method", "logger",                     
                  "item_path", "title_path", "link_path", "summary_path", "thumbnail_path",
                  "attribute_paths", "service_link_paths", "force_decode" ]

    def __init__(self, template, logger):
        """Starts a link to a SnipDex peer.

           @param searchlink    link to (zombi) peer 
           @param mimtetype     snipdex, RSS, Atom, suggestions, html, json, ...
           @param logger        logger
           @param item_path     path to items
           @param title_path    path to title (relative to item)
        """
        self.search_link = template[0]
        self.mimetype = template[1]
        if len(template) > 2:
            self.method = template[2].upper()
        else:
            self.method = 'GET'
        self.logger = logger
        format = FORMAT_NONE
        if re.search("rss", self.mimetype):
            format = FORMAT_RSS
        elif re.search("atom", self.mimetype):
            format = FORMAT_ATOM
        elif self.mimetype == 'application/x-suggestions+xml':
            format = FORMAT_XMLSUGGEST
        elif self.mimetype == 'text/html' and len(template) > 3: # for html we need at least an item_path
            format = FORMAT_HTML
        (self.item_path, self.title_path, self.link_path, self.summary_path, 
            self.thumbnail_path, self.attribute_paths, self.force_decode) = format
        if len(template) > 3 and template[3]: self.item_path       = template[3]
        if len(template) > 4 and template[4]: self.title_path      = template[4]
        if len(template) > 5 and template[5]: self.link_path       = template[5]
        if len(template) > 6 and template[6]: self.summary_path    = template[6]
        if len(template) > 7 and template[7]: self.thumbnail_path  = template[7]
        if len(template) > 8 and template[8]: self.attribute_paths = template[8]
        if len(template) > 9 and template[9]: self.force_decode    = template[9]
       


    def search(self, query, headers=None):
        """Executes a search on the connected peer.
        
           @param query (a query string).
           @return A tuple (peer_list, snippet_list, total_results).
        """
        # opener = urllib2.build_opener()
        #opener.addheaders = [('User-agent', 'Test/0')]
        #html = opener.open('http://www.google.com/search?q='+ urllib2.quote('harvard research computing')).read()

        search_link = query.fill_template_url(self.search_link)
        if search_link.startswith('http://'): 
            search_link = search_link[7:]
            (server, get_link) = search_link.split("/", 1);
            conn = httplib.HTTPConnection(server, timeout=10)
        elif search_link.startswith('https://'):
            search_link = search_link[8:]
            (server, get_link) = search_link.split("/", 1);
            conn = httplib.HTTPSConnection(server, timeout=10)
        #conn.set_debuglevel(1)
        get_link = '/' + get_link
        self.logger.debug("HTTP Connect: " + server)
        if self.method == 'GET':
            (link, body) = (get_link, '')
        else:
            (link, body) = get_link.split('?', 1)
        conn.putrequest(self.method, link, skip_accept_encoding=True)           
        if headers is None:
            headers = SNIPDEX_DEFAULT_HEADERS
        for header in headers:
            (head, argument) = header.split(': ')
            argument = argument.replace('\r\n', '')
            conn.putheader(head, argument)
        if body:
            conn.putheader('Content-Type', 'application/x-www-form-urlencoded')
            conn.putheader('Content-Length', str(len(body)))
            conn.endheaders()
            conn.send(body)
        else:
            conn.endheaders()
        try:
            response = conn.getresponse()
        except httplib.ssl.SSLError:
            raise IOError('SSL going wrong')
        self.logger.debug("HTTP: " + self.method + ", " + self.mimetype + ", " + link + " " + body)
        sockname = response.fp._sock.getsockname()
        if sockname:
            (local_ip, local_port) = (sockname[0], sockname[1]) # get the ip numbers: using _sock is not nice..., also missing some ipv6 stuff?
        sockname = response.fp._sock.getpeername()
        if sockname:
            (peer_ip, peer_port)   = (sockname[0], sockname[1])
        string = response.read()
        conn.close()

        if self.force_decode: # for instance Baidu, charset=gb2312
            try:
                string = string.decode('gb2312', 'ignore').encode('utf-8')
            except:
                pass
            else:
                string = re.sub("charset=" + self.force_decode, "charset=utf-8", string)
        #print "ERRRR:", string
            
        (new_query, peer_list, snippet_list, total_results) = self.parse_peer_response(string)
        new_query.add_key_value('local_ip', local_ip)
        new_query.add_key_value('local_port', local_port)
        new_query.add_key_value('peer_ip', peer_ip)
        new_query.add_key_value('peer_port', peer_port)
        for param in query: 
            if param != 'public_ip' and param != 'public_port':  # careful not to overwrite public_ip, which is given by peer.
                new_query.add_key_value(param, query[param])

        return (new_query, peer_list, snippet_list, total_results)

   
    def parse_peer_response(self, string):
        if self.mimetype == 'application/snipdex+xml':
            return self.parse_peer_response_snipdex(string)
        elif re.search('json', self.mimetype): 
            return self.parse_peer_response_json(string)
        else:
            return self.parse_peer_response_xml(string)


    def parse_peer_response_xml(self, string):
        """Parses an XML peer response. 
        """
        snippet_list = snipdata.SnippetList()
        total_results = None
        string = re.sub(r"xmlns=(\'|\")[^\'\"]*\1", " ", string)  # remove default namespace 
        try:
            if self.mimetype == 'text/html':
                xdoc = libxml2.htmlReadDoc(string, '', None, HTML_PARSE_OPTIONS) 
            else:
                xdoc = libxml2.readDoc(string, '', None, XML_PARSE_OPTIONS)
        except libxml2.treeError:
            raise ValueError('Peer output error.')
        ctxt = xdoc.xpathNewContext()   
        for (name, uri) in re.findall("xmlns:([^\=]*)=[\'\"]([^\'\"]*)", string):
            ctxt.xpathRegisterNs(name, uri) # register all namespaces
            if name == 'opensearch':
                total_results = self.xpath_string_value(ctxt, "//opensearch:totalResults")   
        items = ctxt.xpathEval(self.item_path)
        #print "ITEMS:", items, self.item_path
        right_now = snipdata.right_now()
        for item in items:
            ctxt.setContextNode(item) 
            title     = self.xpath_string_value(ctxt, self.title_path)
            title     = bound_text_no_markup(title, 60)
            link      = self.xpath_link(ctxt, self.link_path)
            attributes = list()
            if self.attribute_paths:
                for key_path in self.attribute_paths.split(','):
                    (key, path) = key_path.split('{', 1)
                    path=path[:-1] # remove trailing '}'
                    value = self.xpath_string_value(ctxt, path)
                    if value:
                        attributes.append((key, value))
            if self.thumbnail_path: # xpath_thumbnail changes: ctxt
                thumbnail = self.xpath_thumbnail(ctxt, self.thumbnail_path)
            else:
                thumbnail = None
            if self.summary_path:
                summary   = self.xpath_string_value(ctxt, self.summary_path)
            else:
                for node in ctxt.xpathEval(self.title_path + '|.//script'):  # remove title and (possibly uncommented) javascript
                    node.unlinkNode()
                summary = self.xpath_string_value(ctxt, '.')
            summary   = bound_text_no_markup(summary, 300)
            snippet = snipdata.Snippet([], link, title, right_now, summary, None, thumbnail, attributes=attributes)
            snippet_list.append(snippet)
        ctxt.xpathFreeContext()
        xdoc.freeDoc()
        new_query = snipdata.Query()
        return (new_query, snipdata.PeerList(), snippet_list, total_results)


    def parse_peer_response_json(self, string):
        """Parses an JSON peer response. 
        """
        raise ValueError('json not supported')


    def parse_peer_response_snipdex(self, string):
        """Parses an Snipdex peer response. 
        """
        peer_list = snipdata.PeerList()
        snippet_list = snipdata.SnippetList()
        xdoc = libxml2.parseDoc(string)
        ctxt = xdoc.xpathNewContext() 
        total_results = self.xpath_string_value(ctxt, "//snippets/total")  # TODO

        # Parse the <query /> part
        new_query = snipdata.Query()
        query_attributes = ctxt.xpathEval("//query/@*")
        for attrib in query_attributes:
            if attrib.content:
                new_query.add_key_value(attrib.name, attrib.content.decode('utf-8', 'ignore'))

        # Parse the <peers> part
        peers = ctxt.xpathEval("//peers/peer")
        for item in peers:
            ctxt.setContextNode(item)
            pid           = self.xpath_string_value(ctxt, "@pid")
            status        = self.xpath_string_value(ctxt, "@status")
            score         = self.xpath_string_value(ctxt, "@score")
            name          = self.xpath_string_value(ctxt, "name")
            description   = self.xpath_string_value(ctxt, "description")
            icon          = self.xpath_string_value(ctxt, "icon")
            updated       = self.xpath_string_value(ctxt, "updated")
            public_address= self.xpath_string_value(ctxt, "public_address")
            local_address = self.xpath_string_value(ctxt, "local_address")
            language      = self.xpath_string_value(ctxt, "language")
            adult_content = self.xpath_string_value(ctxt, "adult_content")
            open_template = self.xpath_url_template(ctxt, "open_template")
            html_template = self.xpath_url_template(ctxt, "html_template")
            query_hints   = self.xpath_string_list(ctxt, "query_hint")
            peer = snipdata.Peer(pid=pid, name=name, description=description, icon=icon, updated=updated, 
                                 language=language, adult_content=adult_content, open_template=open_template, 
                                 html_template=html_template, public_address=public_address, query_hints=query_hints,
                                 local_address=local_address)
            if not status:
                status = 'TODO'
            adult_content = (adult_content == 'True')
            peer_list.append(peer, status, score)

        # Parse the <snippets> part
        snippets = ctxt.xpathEval("//snippets/snippet")
        for item in snippets:
            ctxt.setContextNode(item)
            title        = self.xpath_string_value(ctxt, "title")
            link         = self.xpath_string_value(ctxt, "location")
            summary      = self.xpath_string_value(ctxt, "summary")
            extended_summary = self.xpath_string_value(ctxt, "extended_summary")
            thumbnail    = self.xpath_thumbnail(ctxt, "preview")
            snippet      = snipdata.Snippet([], link, title, "2012-01-01", summary, extended_summary, thumbnail)
            origin_pids  = ctxt.xpathEval("origin/@pid")
            for pid in origin_pids:
                snippet.add_origin(pid.content)
            atts         = ctxt.xpathEval("attributes/attribute")
            for att in atts:
                ctxt.setContextNode(att)
                key   = self.xpath_string_value(ctxt, "@key")
                value = self.xpath_string_value(ctxt, "@value")
                snippet.add_attribute(key, value)
            snippet_list.append(snippet)

        ctxt.xpathFreeContext() # has to be done for libxml2 (C library)
        xdoc.freeDoc()
        return (new_query, peer_list, snippet_list, total_results)


    def reduce_tuple(self, my_tuple):
        result = []
        partial = []
        try:
            for i in my_tuple:
                partial.append(i)
                if i:
                    result = partial[:] # copy list
        except TypeError:
            return my_tuple
        if result:
            return tuple(result)
        else:
            return None


    def xpath_url_template(self, ctxt, xpath):
        return self.reduce_tuple(
           (self.xpath_string_value(ctxt, xpath), 
            self.xpath_string_value(ctxt, xpath + "/@type"), 
            self.xpath_string_value(ctxt, xpath + "/@method"), 
            self.xpath_string_value(ctxt, xpath + "/@item_path"), 
            self.xpath_string_value(ctxt, xpath + "/@title_path"), 
            self.xpath_string_value(ctxt, xpath + "/@link_path"), 
            self.xpath_string_value(ctxt, xpath + "/@summary_path"), 
            self.xpath_string_value(ctxt, xpath + "/@preview_path")))

             
    def xpath_string_value(self, ctxt, xpath, first=True):
        try:
            nodes = ctxt.xpathEval(xpath)
        except libxml2.xpathError: 
            self.logger.debug("XPath Error: " + xpath) 
            return None
        if nodes:
            if first:
                nodes = nodes[0:1] 
            return u" ".join(s.content.decode('utf-8', 'ignore') for s in nodes)
        else:
            return u""

    def xpath_string_list(self, ctxt, xpath): 
        try:
            return list(s.content.decode('utf-8', 'ignore') for s in ctxt.xpathEval(xpath))
        except libxml2.xpathError: 
            #self.logger.debug("XPath Error: " + xpath) 
            return None


    def xpath_link(self, ctxt, xpath):
        """ Returns url.
        """
        try:
            links = ctxt.xpathEval(xpath)
        except libxml2.xpathError:
            #self.logger.debug("XPath Error: " + xpath) 
            return None 
        value = None
        if links:
            for link in links:
                type = self.xpath_string_value(link, "@type")
                value = link.content.decode('utf-8', 'ignore')
                if not value: 
                    value = self.xpath_string_value(link, "@href")
                if not value: 
                    value = self.xpath_string_value(ctxt, "@url")
                if value and type == "text/html":
                    break
        if value == '#':
            value = None
        return value


    def xpath_thumbnail(self, ctxt, xpath):
        """ Returns mimetype, url, and optionally height and width for a thumbnail image.
        """
        try:
            nodes = ctxt.xpathEval(xpath)
        except libxml2.xpathError:
            #self.logger.debug("XPath Error: " + xpath) 
            return None 
        if nodes:
            node = nodes[0] # if there are more, take the first 
            value = node.content.decode('utf-8', 'ignore')
            value = re.sub("\s+", "", value)
            if not value: value = self.xpath_string_value(node, "@url")
            if not value: value = self.xpath_string_value(node, "@source")
            if not value: value = self.xpath_string_value(node, "@href")
            if not value: value = self.xpath_string_value(node, "@src")
            width    = self.xpath_string_value(node, "@width")  
            height   = self.xpath_string_value(node, "@height")
            mimetype = self.xpath_string_value(node, "@type")
            if not mimetype:
                mimetype = "image"
            if value:
                if height:
                    return(mimetype, value, width, height)
                else:
                    return(mimetype, value)
            else:
                return None
        else:
            return None


# Testing...
if (__name__ == '__main__'): 
    import logging
    logger = logging.getLogger("SnipdexSender")
    logging.basicConfig(level=logging.DEBUG, format="%(name)-13s %(message)s")

    new_query = query = snipdata.Query({'q': 'djoerd'})

    mother_peer = snipdata.Peer(pid="5Dv1DzSLYUTnBoGFjPXTBBS", public_address='stable.cs.utwente.nl:8472', )

    # Open cache
    cache = snipdata.SnipdexCache('/tmp/snipdex-cache-127-0-0-1_8472', logger)
    (peer_list, snippet_list) = cache.response_by_query_full(query)
    logger.debug("Cache: " + str(len(peer_list)) + " peers, " + 
                 str(len(snippet_list)) + " results.")

    #peer_list.merge_single(mother_peer, 'TODO')
 
    for time_to_life in range(3): # time to life is 2
        next_peer_list = snipdata.PeerList()
        #logger.debug("PEEEEEEEEEERS:") 
        #for (peer, status, score) in peer_list:
        #    logger.debug("(" + repr(peer) + repr(status) + repr(score) + ")")
        for (peer, status, score) in peer_list:
            if status == 'TODO':
                peer_link = PeerLink(peer.get_open_template(), logger)
                (new_query, new_peer_list, new_snippet_list, total_results) = peer_link.search(query)
                logger.debug("HTTP Response: " + peer.pid + ", " +
                              str(len(new_peer_list)) + " peers, " + 
                              str(len(new_snippet_list)) + " results, " + 
                              "#hops: " + str(time_to_life + 1) + ")")
                if new_snippet_list:
                    new_snippet_list.add_origin(peer.pid)
                    snippet_list.merge(new_snippet_list)
                if new_peer_list: 
                    next_peer_list.merge(new_peer_list)
                next_peer_list.merge_single(peer, 'DONE')
            else:
                next_peer_list.append(peer, status, score)
        peer_list = next_peer_list
        #logger.debug("DOOOONNNEEEE:")
        #for (peer, status, score) in peer_list:
        #    logger.debug("(" + repr(peer) + "," + repr(status) + "," + repr(score) + ")")
                

    #print (new_query, peer_list, snippet_list)


