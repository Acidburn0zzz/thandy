#!/usr/bin/python
# Copyright 2008 The Tor Project.  See LICENSE for licensing information.

import sys
try:
    import py2exe
except ImportError:
    pass

#
#   Current Thandy version
#
VERSION = '0.0.2-alpha'

VERSION_INFO = (0,0,2)

import os, re, shutil, string, struct, sys

os.umask(022)

#======================================================================
# Create startup scripts if we're installing.

if not os.path.isdir("./bin"):
    os.mkdir("./bin")

SCRIPTS = []

def makescripts(extrapath=None):
    del SCRIPTS[:]
    for script_suffix, modname in [ ("server", "ServerCLI"),
                                    ("client", "ClientCLI"),
                                    ("pk", "SignerCLI"), ]:
        fname = os.path.join("./bin", "thandy-%s"%script_suffix)
        if sys.platform == "win32":
            fname += ".py"
        f = open(fname, 'w')
        f.write("#!/bin/sh\n")
        if extrapath:
            f.write('PYTHONPATH="$PYTHONPATH:%s"\n'%extrapath)
            f.write('export PYTHONPATH\n')
        f.write('%s -m thandy/%s "$@"\n' %(sys.executable, modname))
        f.close()
        SCRIPTS.append(fname)

#======================================================================
# Define a helper to let us run commands from the compiled code.
def _haveCmd(cmdname):
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        if os.path.exists(os.path.join(entry, cmdname)):
            return 1
    return 0

def requirePythonDev(e=None):
    if os.path.exists("/etc/debian_version"):
        v = sys.version[:3]
        print "Debian may expect you to install python%s-dev"%v
    elif os.path.exists("/etc/redhat-release"):
        print "Redhat may expect you to install python2-devel"
    else:
        print "You may be missing some 'python development' package for your"
        print "distribution."

    if e:
        print "(Error was: %s)"%e

    sys.exit(1)

try:
    from distutils.core import Command
    from distutils.errors import DistutilsPlatformError
    from distutils.sysconfig import get_makefile_filename
except ImportError, e:
    print "\nUh oh. You have Python installed, but I didn't find the distutils"
    print "module, which is supposed to come with the standard library.\n"

    requirePythonDev()

try:
    # This catches failures to install python2-dev on some redhats.
    get_makefile_filename()
except IOError:
    print "\nUh oh. You have Python installed, but distutils can't find the"
    print "Makefile it needs to build additional Python components.\n"

    requirePythonDev()

#======================================================================
# Now, tell setup.py how to cope.
import distutils.core, distutils.command.install
from distutils.core import setup, Distribution

class InstallCommand(distutils.command.install.install):
    def run(self):
        script_path = None
        sys_path = map(os.path.normpath, sys.path)
        sys_path = map(os.path.normcase, sys_path)
        install_lib = os.path.normcase(os.path.normpath(self.install_lib))

        if install_lib not in sys_path:
            script_path = install_lib

        makescripts(self.install_lib)

        distutils.command.install.install.run(self)

extra_args = { }
if 'py2exe' in sys.argv:
    # Tells the py2exe executable what module to actually execute.
    extra_args["console"] = ['lib/thandy/ClientCLI.py']
    # The following options tell py2exe to create a single exeutable file instead
    # of a directory of dependencies or exe and zip library.
    # Some additional modules are specified explicitly because the way they are
    # loaded prevents py2exe from tracing the dependencies automagically.
    extra_args["zipfile"] = None
    extra_args["options"] = {
                            'py2exe': {
                                      'bundle_files': 1,
                                      'includes': ["linecache", "getopt", "json"]
                            }
    }

# Install the BitTorrent package if it is present.
# XXX If there is an easy way to make sure we're using the patched version
#     of the BitTorrent library, this would be worthwile to detect.
pkg_dir={ '' : 'lib' }
pkgs = ['thandy', 'thandy.packagesys']
for k, dir in pkg_dir.iteritems():
    if os.path.exists(os.path.join(dir, 'BitTorrent')):
        pkgs.append('BitTorrent')
        print "Building with BitTorrent support."

setup(name='Thandy',
      version=VERSION,
      license="3-clause BSD",
      description=
      "Thandy: Secure cross-platform update automation tool.",
      author="Nick Mathewson",
      author_email="nickm@freehaven.net",
      url="http://www.torproject/org",
      package_dir=pkg_dir,
      packages=pkgs,
      scripts=SCRIPTS,
      install_requires=["json", "pycrypto"],
      cmdclass={'install': InstallCommand},
      **extra_args
)

