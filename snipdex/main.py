#!/usr/bin/env python
"""
main.py: Snipdex peer implementation.

Copyright (C) 2011 University of Twente

Authors: Almer S. Tigelaar
         Djoerd Hiemstra

This source file (or any derivates thereof) may not
be distributed and is intended for internal use only. 
"""

import os.path
import sys
import logging
import signal

from optparse import OptionParser
from BaseHTTPServer import HTTPServer 

# Snipdex local imports
import receiver

SNIPDEX_PEER_VERSION = '0.3'

parser = OptionParser(usage="%prog [options]", version=SNIPDEX_PEER_VERSION, 
                      description = "SnipDex Peer")
parser.add_option("-t", "--mother-server", action="store", type="string",
                  dest="mother_server",
                  help="Server name or IP number of the mother peer to use")
parser.add_option("-u", "--mother-port", action="store", type="int",
                  dest="mother_port",
                  help="Port the mother peer runs on")
parser.add_option("-p", "--peer-port", action="store", type="int",
                  dest="peer_port",
                  help="Port the peer runs on")
parser.add_option("-y", "--no-pitch", action="store_true",
                  dest="no_pitch",
                  help="Disables Pitching (for testing purposes)")
parser.add_option("-w", "--web-interface", action="store", dest="web",
                  help="Should the web interface be available and to whom",
                  choices=["disabled", "private", "public"])
parser.add_option("-d", "--debug", action="store_true", dest="debug",
                  help="Show debug messages")
parser.add_option("-l", "--web-location", action="store", type="string",
                  dest="web_location",
                  help="Path that contains the web data used for the web interface.")
parser.add_option("-c", "--cache-file", action="store", type="string",
                  dest="cache_file",
                  help="File-name that contains the cached search results.")


# We assume the main script is not imported.
if (__name__ != '__main__'): 
    sys.stderr.write("Snipdex main.py should not be imported. Please run as: python main.py\n")
    exit(1)

def get_datadir():
    """Get an operating system dependent location to store the cache"""
    home = os.path.expanduser("~")
    if home == '~': #MacOS ?
        datadir = os.path.join(home, 'Library', 'Application Support', 'Snipdex')
    elif home.find('\\') != -1: #Windows?
        datadir = os.path.join(home, '..', 'Application Data', 'Snipdex')
    else: #Linux?
        datadir = os.path.join(home, '.snipdex')
    return datadir

def get_cache_file(cache_prefix, mother_server, mother_port):
    """This is how we define the cache-file"""
    mother_address = mother_server + "_" + str(mother_port)
    return cache_prefix + mother_address.replace(".", "-")

# Get the defaults. 
webroot        = sys.path[0]
webroot        = 'web'.join(webroot.rsplit('snipdex', 1)) # "rrplace: replace the right-most occurrence
mother_server  = 'barn.ewi.utwente.nl'
mother_port    = 8472
datadir        = get_datadir()
cache_prefix   = datadir + os.path.sep + 'snipdex-cache-'
cache_file     = get_cache_file(cache_prefix, mother_server, mother_port)
default_cache  = cache_file 

# Set defaults & parse
parser.set_defaults(peer_port=8472, 
                    mother_server=mother_server, mother_port=mother_port,
                    web_location=webroot, cache_file=cache_file,
                    no_pitch=False, monitor=False, web="private")
(options, args) = parser.parse_args()

# Get mother address and its cache file
if options.mother_server == 'localhost':
    options.mother_server = '127.0.0.1'
if options.cache_file == cache_file:   # no override by user
    options.cache_file = get_cache_file(cache_prefix, options.mother_server, options.mother_port) # other mother, so other default file.
    if not os.path.exists(datadir):
        try:
            os.makedirs(datadir) 
        except OSError:
            sys.stderr.write("Error: Please provide a file name for the Snipdex cache ('-c' option)\n")
            exit(1)

# Initialize logging
logger = logging.getLogger("SnipdexPeer")
if (options.debug):
    logging.basicConfig(level=logging.DEBUG, format="%(name)-11s %(message)s")
else:
    logging.basicConfig(level=logging.INFO, format="# %(message)s")
logger.info("Snipdex peer version " + SNIPDEX_PEER_VERSION)
logger.info("Copyright (C) 2011 University of Twente. All rights reserved.")
logger.debug("Mother's public address: " + options.mother_server + ":" + str(options.mother_port))

# Run web server 
command_handler = receiver.PeerCommandHandler(options.peer_port, options.mother_server, options.mother_port, 
                                              options.web_location, options.cache_file, logger)

if not options.debug:
    receiver.PeerRequestHandler.log_message = lambda *args: None  # no logging
receiver.PeerRequestHandler.command_handler = command_handler
try:
    server = HTTPServer(('', options.peer_port), receiver.PeerRequestHandler)
except receiver.sender.httplib.socket.error as ex:
    sys.stderr.write("Error: SnipDex already running? " + repr(ex) + '\n')
    exit(1)

def cleanup(*args):
    """
    Clean up all the instance variables when exiting
    (Python would garbage collect some of this, but it isn't guaranteed)
    """
    logger.info("Okay, exiting.")
    exit(0)

signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)

logger.info("Search page at: http://127.0.0.1:" + str(options.peer_port) + "/snipdex/")
logger.info("Handling requests, use <Ctrl-C> to terminate")
server.serve_forever()
