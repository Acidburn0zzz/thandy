import thandy.bt_compat
# Copyright 2008 The Tor Project, Inc.  See LICENSE for licensing information.

import getopt
import logging
import sys
import time
import traceback

import thandy.keys
import thandy.formats
import thandy.util
from thandy.util import logCtrl
import thandy.repository
import thandy.download
import thandy.master_keys
import thandy.packagesys.PackageSystem
import thandy.socksurls
import thandy.encodeToXML

json = thandy.util.importJSON()

class ControlLogFormatter:
    def format(self, record):
        name = record.name
        if name == 'thandy-ctrl':
            return record.getMessage()
        else:
            m = record.getMessage()
            return "%s msg=%s"%(record.levelname,
                                thandy.util.formatLogString(m))

    def formatException(self, exc_info):
        return repr(traceback.format_exception(*exc_info))

class RegularLogFilter:
    def filter(self, record):
        return record.name != "thandy-ctrl"

def configureLogs(options):
    logLevel = logging.INFO
    cLogFormat = False
    for o,v in options:
        if o == '--debug':
            logLevel = logging.DEBUG
        elif o == '--info':
            logLevel = logging.INFO
        elif o == '--warn':
            logLevel = logging.WARN
        elif o == '--controller-log-format':
            cLogFormat = True

    console = logging.StreamHandler()
    console.setLevel(logLevel)
    logger = logging.getLogger("")
    logger.addHandler(console)
    logger.setLevel(logLevel)
    if cLogFormat:
        #formatter = logging.Formatter("%(names)s %(levelname)s %(message)r")
        formatter = ControlLogFormatter()
    else:
        formatter = logging.Formatter("%(levelname)s:%(message)s")
        console.addFilter(RegularLogFilter())
    console.setFormatter(formatter)

def update(args):
    repoRoot = thandy.util.userFilename("cache")
    options, args = getopt.getopt(args, "",
        [ "repo=", "no-download", "loop", "no-packagesys",
          "install", "socks-port=", "debug", "info",
          "warn", "force-check", "controller-log-format",
          "download-method="
          ])
    download = True
    keep_looping = False
    use_packagesys = True
    install = False
    socksPort = None
    forceCheck = False
    downloadMethod = "direct"

    for o, v in options:
        if o == '--repo':
            repoRoot = v
        elif o == "--no-download":
            download = False
        elif o == '--loop':
            keep_looping = True
        elif o == '--no-packagesys':
            use_packagesys = False
        elif o == '--install':
            install = True
        elif o == "--socks-port":
            socksPort = int(v)
        elif o == '--force-check':
            forceCheck = True
        elif o == '--download-method':
            downloadMethod = v

    configureLogs(options)

    if socksPort:
        thandy.socksurls.setSocksProxy("127.0.0.1", socksPort)

    if downloadMethod == "bittorrent":
        thandy.bt_compat.BtCompat.setUseBt(True)
    elif downloadMethod != "direct":
        usage()
        sys.exit()

    repo = thandy.repository.LocalRepository(repoRoot)
    downloader = thandy.download.DownloadManager()
    downloader.start()

    # XXXX We could make this loop way smarter.  Right now, it doesn't
    # back off between failures, and it doesn't notice newly downloadable files
    # until all downloading files are finished.
    while True:
        hashes = {}
        lengths = {}
        installable = {}
        btMetadata = {}
        thpTransactions = {}
        logging.info("Checking for files to update.")
        files, downloadingFiles = repo.getFilesToUpdate(
              trackingBundles=args,
              hashDict=hashes,
              lengthDict=lengths,
              usePackageSystem=use_packagesys,
              installableDict=installable,
              btMetadataDict=btMetadata
              thpTransactionDict=thpTransactions)

        if forceCheck:
            files.add("/meta/timestamp.txt")
            forceCheck = False

        if (thpTransactions or installable) and not files:
            for p, d in installable.items():
                for n, i in d.items():
                    if i.canInstall():
                        logCtrl("CAN_INSTALL", PKG=p, ITEM=n)
                    else:
                        logCtrl("NO_INSTALL", PKG=p, ITEM=n)
                    i.setCacheRoot(repoRoot)

            logging.info("Ready to install packages for files: %s",
                           ", ".join(sorted(installable.keys())))
            if install:
                # XXXX handle ordering
                for p in installable.values():
                    for h in p.values():
                        i = h.getInstaller()
                        if i != None:
                            i.install()

            print "Bundles with all THP packages:"
            for bundle in thpTransactions:
              # TODO: ThpTransaction goes here!
              print bundle

            return

        elif not files:
            logging.info("No files to download")
            if not keep_looping:
                return

            ts = repo.getTimestampFile().get()
            age = time.time() - thandy.formats.parseTime(ts['at'])
            delay = thandy.repository.MAX_TIMESTAMP_AGE - age
            if delay > 3600:
                delay = 3600
            elif delay < 0:
                delay = 300
            logging.info("Will check again in %s seconds", delay)
            time.sleep(delay)
            continue

        for f in files: logCtrl("WANTFILE", FILENAME=f)
        logging.info("Files to download are: %s", ", ".join(sorted(files)))

        if not download:
            return

        mirrorlist = repo.getMirrorlistFile().get()
        if not mirrorlist:
            mirrorlist = thandy.master_keys.DEFAULT_MIRRORLIST

        if files:
            waitTill = min(downloader.getRetryTime(mirrorlist, f)
                           for f in files)
            now = time.time()
            if waitTill > now:
                delay = int(waitTill - now) + 1
                logging.info("Waiting another %s seconds before we are willing "
                             "to retry any mirror.", delay)
                time.sleep(delay)
                continue

        logging.debug("Launching downloads")
        now = time.time()
        for f in files:
            if downloader.getRetryTime(mirrorlist, f) > now:
                logging.info("Waiting a while before we fetch %s", f)
                continue

            dj = None
            if thandy.bt_compat.BtCompat.shouldUseBt() and downloadingFiles:
                dj = thandy.download.ThandyBittorrentDownloadJob(
                    repo.getFilename(btMetadata[f]), f,
                    repo.getFilename(f),
                    wantHash=hashes.get(f),
                    wantLength=lengths.get(f),
                    repoFile=repo.getRequestedFile(f))

            else:
                dj = thandy.download.ThandyDownloadJob(
                    f, repo.getFilename(f),
                    mirrorlist,
                    wantHash=hashes.get(f),
                    wantLength=lengths.get(f),
                    repoFile=repo.getRequestedFile(f),
                    useTor=(socksPort!=None))

            def successCb(rp=f):
                rf = repo.getRequestedFile(rp)
                if rf != None:
                    rf.clear()
                    rf.load()
            def failCb(): pass
            dj.setCallbacks(successCb, failCb)

            downloader.addDownloadJob(dj)

        logging.debug("Waiting for downloads to finish.")
        downloader.wait()
        logging.info("All downloads finished.")

def json2xml(args):
    if len(args) != 1:
        usage()
    f = open(args[0], 'r')
    obj = json.load(f)
    f.close()
    thandy.encodeToXML.encodeToXML(obj, sys.stdout.write)

def usage():
    print "Known commands:"
    print "  update [--repo=repository] [--no-download] [--loop]"
    print "         [--no-packagesys] [--install] [--socks-port=port]"
    print "         [--debug|--info|--warn] [--force-check]"
    print "         [--controller-log-format]"
    print "         [--download-method=direct|bittorrent]"
    print "         bundle1, bundle2, ..."
    print "  json2xml file"
    sys.exit(1)

def main():

    if len(sys.argv) < 2:
        usage()
    cmd = sys.argv[1]
    args = sys.argv[2:]
    if cmd in [ "update", "json2xml" ]:
        globals()[cmd](args)
    else:
        usage()

if __name__ == '__main__':
    main()
