# Copyright 2011 The Tor Project, Inc.  See LICENSE for licensing information.

import logging
import os
import zipfile
import tempfile
import time
import shutil
import subprocess
import sys

from lockfile import LockFile, AlreadyLocked, LockFailed

import thandy.util
import thandy.formats
import thandy.packagesys.PackageSystem as PS
import thandy.packagesys.PackageDB as PDB

json = thandy.util.importJSON()

class ThpDB(object):
    def __init__(self):
        self._upgrade = False
        self._thp_db_root = os.environ.get("THP_DB_ROOT")
        if self._thp_db_root is None:
          raise Exception("There is no THP_DB_ROOT variable set")

    def getPath(self):
        return self._thp_db_root

    def startUpgrade(self):
        self._upgrade = True

    def finishUpgrade(self, name):
        fname = os.path.join(self._thp_db_root, "pkg-status", name+".json")
        shutil.move(fname+".new", fname)
        self._upgrade = False

    def isUpgrading(self):
        return self._upgrade

    def insert(self, pkg):
        fname = os.path.join(self._thp_db_root, "pkg-status",
                             pkg['package_name']+".json")
        if self._upgrade:
            fname += ".new"

        thandy.util.replaceFile(fname,
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

class ThpTransaction(object):
    def __init__(self, packages, repoRoot):
        self._raw_packages = packages
        self._repo_root = repoRoot
        self._installers = []
        self._db = ThpDB()

        self._process()

    def _process(self):
        for package in self._raw_packages.keys():
            self._installers.append(ThpInstaller(self._raw_packages[package]['files'][0][0],
                                    self._db,
                                    self._repo_root))

    def _orderByDep(self):
        """ Orders packages with a topological order by its dependencies """
        return self._installers

    def install(self):
        lockfile = os.path.join(self._db.getPath(), "db")
        lock = LockFile(lockfile)
        try:
            print "Acquiring lock..."
            lock.acquire()
            print "Lock acquired"
            order = self._orderByDep()
            for pkg in order:
                if pkg.run('checkinst') != 0:
                    print "Check inst failed for %s" % pkg
                    sys.exit(1)
            for pkg in order:
                print "Starting installation using", pkg
                if pkg.run('preinst') != 0:
                    print "Preinst script for %s failed" % pkg
                    sys.exit(1)
                pkg.install()
        except AlreadyLocked:
            print "You can't run more than one instance of Thandy"
        except LockFailed:
            print "Can't acquire lock on %s" % lockfile
        finally:
            lock.release()

    def remote(self):
        raise NotImplemented()

class ThpInstaller(PS.Installer):
    def __init__(self, relPath, db = None, repoRoot = None):
        PS.Installer.__init__(self, relPath)
        self._db = db
        self.setCacheRoot(repoRoot)
        if db is None:
            self._db = ThpDB()
        self._pkg = ThpPackage(os.path.join(self._cacheRoot, self._relPath[1:]))

    def __repr__(self):
        return "ThpInstaller(%r)" %(self._relPath)

    def install(self):
        print "Running thp installer", self._cacheRoot, self._relPath
        self._thp_root = os.environ.get("THP_INSTALL_ROOT")
        if self._thp_root is None:
            raise Exception("There is no THP_INSTALL_ROOT variable set")

        destPath = os.path.join(self._thp_root, self._pkg.get("package_name"))
        print "Destination directory:", destPath

        if self._db.exists(self._pkg.get("package_name")):
            print "%s is already installed, switching to upgrade mode." % self._pkg.get("package_name")
            self._db.startUpgrade()

        pkg_metadata = self._pkg.getAll()
        self._db.insert(pkg_metadata)
        self._db.statusInProgress(pkg_metadata)

        dir = os.path.join(self._thp_root, self._pkg.get("package_name"))
        try:
            os.mkdir(dir)
        except:
            print "%s: Already exists, using it." % dir

        for file in self._pkg.get('manifest'):
            if file['is_config']:
                print "Ignoring file:", file
            else:
              print "Processing file:", file
              try:
                  # Create all the needed dirs
                  os.makedirs(os.sep.join((os.path.join(destPath, file['name'])
                    .split(os.path.sep)[:-1])))
              except:
                  # Ignore if it already exists
                  pass
              shutil.copy(os.path.join(self._pkg.getTmpPath(), "content", file['name']),
                              os.path.join(destPath, file['name']));

        if self._db.isUpgrading():
            print "Finishing upgrade."
            self._db.finishUpgrade(self._pkg.get('package_name'))

        self._db.statusInstalled(pkg_metadata)

    def remove(self):
        print "Running thp remover"

    def getDeps(self):
        return self._pkg.getDeps()

    def run(self, key):
        return self._pkg.run(key)

class ThpPackage(object):
    def __init__(self, thp_path):
        self._thp_path = thp_path
        self._metadata = None
        self._valid = False
        self._tmp_path = ""
        self._scripts = {}

        self._process()

    def __del__(self):
        thandy.util.deltree(self._tmp_path)

    def __repr__(self):
        print "ThpPackage(%s)" % self._thp_path

    def _process(self):
        self._tmp_path = tempfile.mkdtemp(suffix=str(time.time()),
                                   prefix="thp")

        thpFile = zipfile.ZipFile(self._thp_path)
        thpFile.extractall(self._tmp_path)
        json_file = os.path.join(self._tmp_path, "meta", "package.json")
        contents = open(os.path.join(self._tmp_path, "meta", "package.json")).read()
        self._metadata = json.loads(contents)
        (allOk, where) = self._validateFiles(self._tmp_path)

        if not allOk:
            print "These files have different digests:"
            print where
            sys.exit(1)

        if "scripts" in self._metadata:
            if "python2" in self._metadata['scripts']:
                for script in self._metadata['scripts']['python2']:
                    env = {}
                    env['THP_PACKAGE_NAME'] = self._metadata['package_name']
                    env['THP_OLD_VERSION'] = ""
                    env['THP_NEW_VERSION'] = self._metadata['package_version']
                    env['THP_OLD_INSTALL_ROOT'] = ""
                    env['THP_INSTALL_ROOT'] = os.getenv("THP_INSTALL_ROOT")
                    env['THP_JSON_FILE'] = json_file
                    env['THP_VERBOSE'] = 1
                    env['THP_PURGE'] = 0
                    env['THP_TEMP_DIR'] = self._tmp_path

                    sw = ScriptWrapper(os.path.join(self._tmp_path, "meta", 
                                       "scripts", script[0]), env)

                    for type in script[1]:
                        self._scripts[type] = sw
            else:
                sys.exit(1)

    def get(self, key):
        if self._metadata:
            return self._metadata.get(key)

    def getAll(self):
        return self._metadata

    def getDeps(self):
        if 'require_packages' in self._metadata.keys():
            return self._metadata['require_packages']

    def isValid(self):
        return self._valid

    def getTmpPath(self):
        return self._tmp_path

    def _validateFiles(self, tmpPath):
        for manifest in self._metadata['manifest']:
            name = manifest['name']
            digest = manifest['digest']
            is_config = manifest['is_config']
            f = open(os.path.join(tmpPath, "content", name), "rb")
            newdigest = thandy.formats.formatHash(thandy.formats.getFileDigest(f))
            f.close()
            if newdigest != digest:
                return (False, [name, digest, newdigest])
        return (True, None)

    def run(self, key):
        if key in self._scripts.keys():
            return self._scripts[key].run()
        return 0

class ScriptWrapper(object):
    def __init__(self, path = None, env = None):
        self._path = path
        self._env = None

    def run(self):
        self._process = subprocess.Popen(["python", self._path], 
                                         env=self._env)
        return self._process.returncode
