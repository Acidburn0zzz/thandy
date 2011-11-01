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
    """ Represents the installed (or not) Thp Packages in the system """

    def __init__(self):
        self._upgrade = False
        self._thp_db_root = os.environ.get("THP_DB_ROOT")
        if self._thp_db_root is None:
          raise Exception("There is no THP_DB_ROOT variable set")
        dbpath = os.path.join(self._thp_db_root, "pkg-status")
        try:
            os.mkdir(dbpath)
        except OSError, e:
            pass

    def getPath(self):
        """ Returns the path to the database root """
        return self._thp_db_root

    def startUpgrade(self):
        """ Called when an upgrade of a package starts """
        self._upgrade = True

    def finishUpgrade(self, name):
        """ Called when an upgrade of a package finishes.
            If something goes wrong, this isn't called, and it will be
            detected next time """
        fname = os.path.join(self._thp_db_root, "pkg-status", name+".json")
        shutil.move(fname+".new", fname)
        self._upgrade = False

    def isUpgrading(self):
        return self._upgrade

    def insert(self, pkg):
        """ Adds an entry in the database for the package. If it's an
            upgrade, it means that there's already an entry for this
            package, so it adds a ".new" to the name. """
        fname = os.path.join(self._thp_db_root, "pkg-status",
                             pkg['package_name']+".json")
        if self._upgrade:
            fname += ".new"

        thandy.util.replaceFile(fname,
                                json.dumps(pkg))

    def delete(self, pkg):
        """ Removes an entry from the database. """
        try:
          os.unlink(os.path.join(self._thp_db_root, "pkg-status",
                                 pkg['package_name'])+".json")
        except Exception as e:
          print e

    def update(self, pkg):
        self.insert(pkg)

    def exists(self, name):
        """ Returns a tuple (fexists, version, status). Which
            represent a boolean that is true if the entry exists, the
            version of the package installed, and the status of the
            installation (in case the previous installation went wrong
            somehow) respectively. """
        fname = os.path.join(self._thp_db_root, "pkg-status", name+".json")
        fexists = os.path.exists(fname)

        version = -1
        if fexists:
            contents = open(fname, "r").read()
            metadata = json.loads(contents)
            version = metadata['package_version']

        fname = os.path.join(self._thp_db_root, "pkg-status", name+".status")
        fexists2 = os.path.exists(fname)

        status = ""
        if fexists2:
            contents = open(fname, "r").read()
            metadata = json.loads(contents)
            status = metadata['status']

        return fexists, version, status

    def statusInProgress(self, pkg):
        """ Updates the status of a package entry to "IN-PROGRESS". """
        thandy.util.replaceFile(os.path.join(self._thp_db_root, "pkg-status",
                                             pkg['package_name']+".status"),
                                json.dumps({ "status" : "IN-PROGRESS" }))

    def statusInstalled(self, pkg):
        """ Updates the status of a package entry to "INSTALLED". """
        thandy.util.replaceFile(os.path.join(self._thp_db_root, "pkg-status",
                                             pkg['package_name']+".status"),
                                json.dumps({ "status" : "INSTALLED" }))

class ThpChecker(PS.Checker):
    """ Installation checker for Thp packages. """
    def __init__(self, name, version):
        PS.Checker.__init__(self)
        self._name = name
        self._version = version
        self._db = ThpDB()

    def __repr__(self):
        return "ThpChecker(%r, %r)"%(self._name, self._version)

    def getInstalledVersions(self):
        """ Returns a tuple (version, status). Which represent a list
            of versions of the installed packages and the status of the
            installation. """
        versions = []
        (exists, version, status) = self._db.exists(self._name)

        if exists:
            versions.append(version)

        return versions, status

    def isInstalled(self):
        """ Returns true if the package is installed properly. """
        versions, status = self.getInstalledVersions()
        # if status = IN_PROGRESS a previous installation failed
        # we need to reinstall
        return (status == "INSTALLED" and self._version in versions)

class ThpTransaction(object):
    """ Represents the installation of a bundle that contains thp packages. """
    def __init__(self, packages, alreadyInstalled, repoRoot):
        self._raw_packages = packages
        self._repo_root = repoRoot
        self._installers = []
        self._alreadyInstalled = alreadyInstalled
        self._db = ThpDB()

        self._process()

    def _process(self):
        """ Generates a list of ThpInstallers depending on whether the
            package is already installed or not. """
        for package in self._raw_packages.keys():
            if not (self._raw_packages[package]['files'][0][0] in self._alreadyInstalled):
                self._installers.append(ThpInstaller(self._raw_packages[package]['files'][0][0],
                                                     self._db,
                                                     self._repo_root))

    def isReady(self):
        """ A transaction is ready to be installed if it has at least
            one installer to be used. """
        return (len(self._installers) > 0)

    def _orderByDep(self):
        """ Orders packages with a topological order by its
            dependencies (not implemented, obviously). """
        return self._installers

    def install(self):
        """ Installs the packages that belong to the transaction. """
        lockfile = os.path.join(self._db.getPath(), "db")
        lock = LockFile(lockfile)
        try:
            logging.info("Acquiring lock...")
            lock.acquire()
            logging.info("Lock acquired")
            order = self._orderByDep()
            for pkg in order:
                if pkg.run('checkinst') != 0:
                    logging.info("Check inst failed for %s" % pkg)
                    sys.exit(1)
            for pkg in order:
                logging.info("Starting installation using %s" % pkg)
                if pkg.run('preinst') != 0:
                    logging.info("Preinst script for %s failed" % pkg)
                    sys.exit(1)
                pkg.install()
                if pkg.run('postinst') != 0:
                    logging.info("postinst script failed")
        except AlreadyLocked:
            print "You can't run more than one instance of Thandy"
        except LockFailed:
            print "Can't acquire lock on %s" % lockfile
        finally:
            logging.info("Releasing lock...")
            lock.release()

    def remove(self):
        raise NotImplemented()

class ThpInstaller(PS.Installer):
    """ Represents an installer for an individual Thp package. """
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
        """ Installs the Thp package (copies the file structure to the installation root). """
        logging.info("Running thp installer %s %s" % (self._cacheRoot, self._relPath))
        self._thp_root = os.environ.get("THP_INSTALL_ROOT")
        if self._thp_root is None:
            raise Exception("There is no THP_INSTALL_ROOT variable set")

        destPath = os.path.join(self._thp_root, self._pkg.get("package_name"))
        logging.info("Destination directory: %s" % destPath)

        (exists, _, _) = self._db.exists(self._pkg.get("package_name"))
        if exists:
            logging.info("%s is already installed, switching to upgrade mode." % self._pkg.get("package_name"))
            self._db.startUpgrade()
        
        pkg_metadata = self._pkg.getAll()
        self._db.insert(pkg_metadata)
        self._db.statusInProgress(pkg_metadata)

        dir = os.path.join(self._thp_root, self._pkg.get("package_name"))
        try:
            os.mkdir(dir)
        except:
            logging.info("%s: Already exists, using it." % dir)

        for file in self._pkg.get('manifest'):
            if file['is_config']:
                logging.info("Ignoring file: %s" % file)
            else:
              logging.info("Processing file: %s" % file)
              try:
                  # Create all the needed dirs
                  os.makedirs(os.path.join((os.path.join(destPath, file['name'])
                    .split("/")[:-1])))
              except:
                  # Ignore if it already exists
                  pass
              shutil.copy(os.path.join(self._pkg.getTmpPath(), "content", file['name']),
                              os.path.join(destPath, file['name']));

        if self._db.isUpgrading():
            logging.info("Finishing upgrade.")
            self._db.finishUpgrade(self._pkg.get('package_name'))

        self._db.statusInstalled(pkg_metadata)

    def remove(self):
        print "Running thp remover"

    def getDeps(self):
        return self._pkg.getDeps()

    def run(self, key):
        return self._pkg.run(key)

class ThpPackage(object):
    """ Represents a Thp Package. """
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
        """ Extracts the package, validates its files and creates the
            ScriptWrappers. """
        self._tmp_path = tempfile.mkdtemp(suffix=str(time.time()),
                                   prefix="thp")

        thpFile = zipfile.ZipFile(self._thp_path)
        thpFile.extractall(self._tmp_path)
        json_file = os.path.join(self._tmp_path, "meta", "package.json")
        contents = open(os.path.join(self._tmp_path, "meta", "package.json")).read()
        self._metadata = json.loads(contents)
        (allOk, where) = self._validateFiles(self._tmp_path)

        if not allOk:
            logging.info("These files have different digests:")
            logging.info(where)
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
        """ Accessor for a metadata key. """
        if self._metadata:
            return self._metadata.get(key)

    def getAll(self):
        """ Accessor to all the metadata. """
        return self._metadata

    def getDeps(self):
        """ Return the dependencies especified in the metadata. """
        if 'require_packages' in self._metadata.keys():
            return self._metadata['require_packages']

    def isValid(self):
        return self._valid

    def getTmpPath(self):
        return self._tmp_path

    def _validateFiles(self, tmpPath):
        """ Validates the files based on the manifest
            information. Returns a list of invalid files, in case they are
            found. """
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
        """ Executes a script from the package. """
        if key in self._scripts.keys():
            return self._scripts[key].run()
        return 0

class ScriptWrapper(object):
    """ Wrapper for the scripts in the Thp package. """
    def __init__(self, path = None, env = None):
        self._path = path
        self._env = None

    def run(self):
        """ Abstracts how a script is executed. In this case, another
            python instance is executed with the necessary env. """
        self._process = subprocess.Popen(["python", self._path], 
                                         env=self._env)
        self._process.wait()
        return self._process.returncode
