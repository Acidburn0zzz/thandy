# THP config file creation

VIDALIA_THP_NAME=Vidalia.app
VIDALIA_THP_VERSION=0.3.1 # this has dots, the one you use with thpconfig has commas!
VIDALIA_FILES=/Application/Vidalia.app/

OLD_FILELIST=${VIDALIA_THP_NAME}-${VIDALIA_THP_VERSION}_thp.filelist.old
VIDALIA_CONFIGS=${VIDALIA_THP_NAME}.configs

# output: thp_name-version_thp.cfg => Vidalia.app-0.3.1_thp.cfg
python lib/thandy/ThpHelper.py thpconfig \
    --thp_name=${VIDALIA_THP_NAME} \
    --version_list=0,3,1 \ # this gets converted to 0.3.1 to be used inside
    --scan=${VIDALIA_FILES} \
    --os=lin \
    --arch=x86 \
    --scripts="['markExecutable.py', ['postinst']]" \
    --generate_file_list=1 \
    --old_file_list=${OLD_FILELIST}
    --config_file_list=${VIDALIA_CONFIGS}

# At this point, the idea would be to check whether there are new
# files or not in the list comapred to the old list, mark the
# configuration files as such and adding them to the config file list
# file. Once that's done:

# the new file is the old file list for next time
mv ${VIDALIA_THP_NAME}-${VIDALIA_THP_VERSION}_thp.filelist ${OLD_FILELIST}

# THP file creation

THANDY_MASER_REPO=repo/

THP_DEST=${THP_MASTER_REPO}/data/
KEY=jJkr8wi # this is just an example, but it would be fixed in the real world situation

VIDALIA_THP_CONFIG=${VIDALIA_THP_NAME}-${VIDALIA_THP_VERSION}_thp.cfg
VIDALIA_SCRIPTS=bootstrap_configs/vidalia_structure/scriptsDir/

python lib/thandy/ThpCLI.py makethppackage \
    ${VIDALIA_THP_CONFIG} \
    ${VIDALIA_FILES} \
    ${THP_DEST} \
    ${VIDALIA_SCRIPTS}

# Thandy package/bundle config creation

python lib/thandy/ConfigCLI.py packageconfig \
    --app_name=Vidalia.app \
    --version_list="0,3,1" \
    --location=/pkginfo/vidalia/vidalia-0.3.1.txt \
    --short_desc="Multiplatform tor controller" \
    --long_desc="Vidalia NG is a new generation of the multiplatform tor controller." \
    --dest="TorBrowser.app/Contents/MacOS/Vidalia.app" \

python lib/thandy/ConfigCLI.py packageconfig \
    --app_name=Firefox.app \
    --version_list="9,1" \
    --location=/pkginfo/firefox/firefox-9.1.txt \
    --short_desc="Web browser" \
    --long_desc="Tor friendly web broser." \
    --dest="TorBrowser.app/Contents/MacOS/Firefox.app" \

python lib/thandy/ConfigCLI.py bundleconfig \
    --bundle_name="Tor Browser Bundle" \
    --version_list="1,2,3" \
    --bundle_location=/bundleinfo/tbb/tbb-1.2.3.txt \
    --os=lin \
    --arch=x86 \
    --short_gloss="short gloss" \
    --long_gloss="this is the long glossary" \
    --pkg_names="Vidalia.app,Firefox.app"

VIDALIA_PKG_CONFIG=bootstrap_configs/vidalia-0.3.1_package.cfg 
VIDALIA_PKG=vidalia-0.3.1.txt
VIDALIA_THP=${THP_DEST}/Vidalia.app-0.3.1.thp

VIDALIA_BUNDLE_CONFIG=bootstrap_configs/vidalia-0.3.1.cfg
VIDALIA_BUNDLE=vidalia-bundle-0.3.1.txt

python lib/thandy/SignerCLI.py makepackage --keyid=${KEY} ${VIDALIA_PKG_CONFIG} ${VIDALIA_THP}
python lib/thandy/SignerCLI.py makebundle --keyid=${KEY} ${VIDALIA_BUNDLE_CONFIG} ${VIDALIA_PKG}
python lib/thandy/ServerCLI.py insert ${VIDALIA_PKG} ${VIDALIA_BUNDLE}
