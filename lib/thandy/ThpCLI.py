# Copyright 2011 The Tor Project, Inc.  See LICENSE for licensing information.

import sys
import os
import getopt
import tempfile
import time
import shutil
import zipfile

import thandy.keys
import thandy.util
import thandy.formats

json = thandy.util.importJSON()

def makethppackage(args):
    options, args = getopt.getopt(args, "", "keyid=")
    keyid = None
    scriptsPath = None
    for o,v in options:
        if o == "--keyid":
            keyid = v

    if len(args) < 3:
        usage()

    tmpPath = tempfile.mkdtemp(suffix=str(time.time()),
                               prefix="thp")

    print "Using temporary directory: %s" % tmpPath

    configFile = args[0]
    dataPath = args[1]
    thpPath = args[2]
    if len(args) > 3:
      scriptsPath = args[3]

    print "Generating package metadata..."
    metadata = thandy.formats.makeThpPackageObj(configFile, dataPath)

    print "Generating directory structure..."

    thandy.util.replaceFile(os.path.join(tmpPath, "package.json"),
                            json.dumps(metadata, indent=3))

    thpFileName = "%s-%s.thp" % (metadata['package_name'],
                                 metadata['package_version'])

    print "Generating thp file in %s" % thpFileName
    thpFile = zipfile.ZipFile(os.path.join(thpPath,
                                           thpFileName), "w")

    for file in metadata['manifest']:
        thpFile.write(os.path.join(dataPath, file['name']),
                      os.path.join("content", file['name']))

    if "scripts" in metadata:
      for lang in metadata["scripts"]:
        for script in metadata['scripts'][lang]:
          thpFile.write(os.path.join(scriptsPath, script[0]),
                        os.path.join("meta", "scripts", script[0]))

    thpFile.write(os.path.join(tmpPath, "package.json"),
                  os.path.join("meta", "package.json"))

    thpFile.close()

    print "All done. Cleaning tmp directory..."
    thandy.util.deltree(tmpPath)

def usage():
    print "Known commands:"
    print "  makethppackage config datapath thpPath scriptsPath"
    sys.exit(1)

def main():
    if len(sys.argv) < 2:
        usage()
    cmd = sys.argv[1]
    args = sys.argv[2:]
    if cmd in [ "makethppackage", ]:
        try:
            globals()[cmd](args)
        except thandy.BadPassword:
            print >>sys.stderr, "Password incorrect."
    else:
        usage()

if __name__ == '__main__':
    main()
