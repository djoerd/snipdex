!/usr/bin/env python

"""setup.py: SnipDex redistributable setup (not working at the moment)

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

# NOTE: Python expects us to have a certain package-tree
# layout. In fact they prefer everything as we have it now,
# but then one level deeper (e.g. in a "snipdex" directory).
# The setup script is intended to run _outside_ of that
# directory. So I've solved this for now by going to
# one-directory above the (current) snipdex dir.
#
# This has a couple of consequences:
# 1) There should be no other Python package directories
#    at the same level as "snipdex/"
# 2) Package generation will generate "build", "bdist"
#     and "egg" directories one-level above
#     "snipdex/" (you should remove these manually)
#
# We could alternatively move everything one-level down,
# but this doesn't have a high priority on my wishlist - AT.
#

from setuptools import setup, find_packages
 

setup(name="snipdex",
      version='0.3', # NICER to use SNIPDEX_VERSION, but we'll do it like this for now
      description="A Peer-to-Peer Web Search Application",
      long_description="""
SnipDex is a Web Search Engine that runs on your computer
and the computers of many other people like you. It provides
a Web Search experience free of advertisements, with all your
data completely under your control.
""",
      author="Almer S. Tigelaar",
      author_email="almer@snipdex.org",
      maintainer="Almer S. Tigelaar",
      maintainer_email="almer@snipdex.org",
      url="http://www.snipdex.org",
      download_url="http://www.snipdex.org/download/",
      packages=find_packages(),
      package_data = {
                # NOTE: If you add / change anything here, you MUST also
                # do this in MANIFEST.in, otherwise the files will not
                # be included in the source distribution.
                "snipdex" : [ "web/*.*" ],
                },
      entry_points = {
                "console_scripts" : [
                        "snipdex = snipdex.run:__main__",
                ]},

      # NOTE: Changing / updating dependencies here? don't forget
      # to adjust stdeb.cfg for Debian package generation.
      install_requires = [
#                "setuptools >= 0.6", # Hmmm, I think setuptools should be added, but doesn't work this way
                "feedparser >= 4.1",
                "m2crypto >= 0.19.1",
                ],
      classifiers=[
                "Development Status :: 2 - Pre-Alpha",
                "Environment :: Console",
                "Environment :: Web Environment",
                "Intended Audience :: Science/Research",
                "License :: Other/Proprietary License", # [AT: For now, the "in-house" phase, I will change this later]
                "Operating System :: OS Independent",
                "Programming Language :: Python :: 2.6",
                "Topic :: Internet :: WWW/HTTP :: Indexing/Search",
                ]
      )

# NOTE:
# Consider adding test_suite to the above to be able to run
#   python setup.py test
