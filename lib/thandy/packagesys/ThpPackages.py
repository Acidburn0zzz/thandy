# Copyright 2011 The Tor Project, Inc.  See LICENSE for licensing information.

import logging
import os
import zipfile
import tempfile
import time

import thandy.util
import thandy.packagesys.PackageSystem as PS
import thandy.packagesys.PackageDB as PDB

json = thandy.util.importJSON()

class ThpDB(object):
    def __init__(self):
        self._thp_db_root = os.environ.get("THP_DB_ROOT")
        if self._thp_db_root is None:
          raise Exception("There is no THP_DB_ROOT variable set")

    def insert(self, pkg):
        thandy.util.replaceFile(os.path.join(self._thp_db_root, "pkg-status",
                                             pkg['package_name'])+".json",
                                json.dumps(pkg))

    def delete(self, pkg):
        try:
          os.unlink(os.path.join(self._thp_db_root, "pkg-status",
                                 pkg['package_name'])+".json")
        except Exception as e:
          print e

    def update(self, pkg):
        self.insert(pkg)

    def exists(self, name):
        fname = os.path.join(self._thp_db_root, "pkg-status", name+".json")
        fexists = os.path.exists(fname)

        version = -1
        if fexists:
            contents = open(fname, "r").read()
            metadata = json.loads(contents)
            version = metadata['package_version']
        return fexists, version

    def statusInProgress(self, pkg):
        thandy.util.replaceFile(os.path.join(self._thp_db_root, "pkg-status",
                                             pkg['package_name']+".status"),
                                json.dumps({ "status" : "IN-PROGRESS" }))

    def statusInstalled(self, pkg):
        thandy.util.replaceFile(os.path.join(self._thp_db_root, "pkg-status",
                                             pkg['package_name']+".status"),
                                json.dumps({ "status" : "INSTALLED" }))

class ThpChecker(PS.Checker):
    def __init__(self, name, version):
        PS.Checker.__init__(self)
        self._name = name
        self._version = version
        self._db = ThpDB()

    def __repr__(self):
        return "ThpChecker(%r, %r)"%(self._name, self._version)

    def getInstalledVersions(self):
        versions = []
        (exists, version) = self._db.exists(self._name)

        if exists:
            versions.append(version)

        return versions

    def isInstalled(self):
        return self._version in self.getInstalledVersions()

class ThpInstaller(PS.Installer):
    def __init__(self, relPath):
        PS.Installer.__init__(self, relPath)
        self._db = ThpDB()

    def __repr__(self):
        return "ThpInstaller(%r)" %(self._relPath)

    def install(self):
        print "Running thp installer", self._cacheRoot, self._relPath
        self._thp_root = os.environ.get("THP_INSTALL_ROOT")
        if self._thp_root is None:
          raise Exception("There is no THP_INSTALL_ROOT variable set")

        pkg = ThpPackage(os.path.join(self._cacheRoot, self._relPath[1:]))
        self._db.insert(pkg.getAll())
#        self._db.delete(pkg.getAll())
        print self._db.exists(pkg.get("package_name"))

#        shutil.copytree()

    def remove(self):
        print "Running thp remover"

class ThpPackage(object):
    def __init__(self, thp_path):
        self._thp_path = thp_path
        self._metadata = None

        self._process()

    def __repr__(self):
        print "ThpPackage(%s)" % self._thp_path

    def _process(self):
        tmpPath = tempfile.mkdtemp(suffix=str(time.time()),
                                  prefix="thp")

        thpFile = zipfile.ZipFile(self._thp_path)
        thpFile.extractall(tmpPath)
        contents = open(os.path.join(tmpPath, "meta", "package.json")).read()
        self._metadata = json.loads(contents)

        thandy.util.deltree(tmpPath)

    def get(self, key):
        if self._metadata:
          return self._metadata.get(key)

    def getAll(self):
        return self._metadata
