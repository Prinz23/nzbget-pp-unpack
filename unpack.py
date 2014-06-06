#!/usr/bin/env python
#
##############################################################################
### NZBGET POST-PROCESSING SCRIPT                                          ###

# Unpack ".rar" files.
#
# This script unpacks rar files from the download directory.
#
# NOTE: This script requires Python to be installed on your system.
# Linux only!
# Needs unrar for .rar archives, unzip for .zip archives, 7z for 7z archives

##############################################################################
### OPTIONS                                                                ###

# Media Extensions
#
# This is a list of media extensions that may be deleted if ".sample" is in the filename.
# NOTE: only .rar,.zip,.7z supported
#unpackExtensions=.rar,.zip,.7z


# minFileSize
#
# This is the minimum size (in MiB) to be be considered as archive file to unpack.
#minSize=200

### NZBGET POST-PROCESSING SCRIPT                                          ###
##############################################################################

import os
import sys
import subprocess
import re
import time

def is_small(filePath, inputName, minSize):
    # 200 MB in bytes
    SIZE_CUTOFF = int(minSize) * 1024 * 1024
    # Ignore 'subs' in files unless 'subs' in Torrent Name
    return (not 'subs' in filePath.lower()) and (not 'subs' in inputName) and (os.path.getsize(filePath) < SIZE_CUTOFF)


# NZBGet V11+
# Check if the script is called from nzbget 11.0 or later
if os.environ.has_key('NZBOP_SCRIPTDIR') and not os.environ['NZBOP_VERSION'][0:5] < '11.0':
    print "[INFO] Script triggered from NZBGet (11.0 or later)."

    # NZBGet argv: all passed as environment variables.
    clientAgent = "nzbget"
    # Exit codes used by NZBGet
    POSTPROCESS_PARCHECK=92
    POSTPROCESS_SUCCESS=93
    POSTPROCESS_ERROR=94
    POSTPROCESS_NONE=95

    # Check nzbget.conf options
    status = 0

    if os.environ['NZBOP_UNPACK'] != 'yes':
        print "[INFO] Please enable option \"Unpack\" in nzbget configuration file, exiting"
        sys.exit(POSTPROCESS_NONE)

    # Check par status
    if os.environ['NZBPP_PARSTATUS'] == '3':
        print "[INFO] Par-check successful, but Par-repair disabled, exiting"
        sys.exit(POSTPROCESS_NONE)

    if os.environ['NZBPP_PARSTATUS'] == '1':
        print "[INFO] Par-check failed, setting status \"failed\""
        status = 1
        sys.exit(POSTPROCESS_NONE)

    # Check unpack status
    if os.environ['NZBPP_UNPACKSTATUS'] == '1':
        print "[INFO] Unpack failed, setting status \"failed\""
        status = 1
        sys.exit(POSTPROCESS_NONE)

    if os.environ['NZBPP_UNPACKSTATUS'] == '0' and os.environ['NZBPP_PARSTATUS'] != '2':
        # Unpack is disabled or was skipped due to nzb-file properties or due to errors during par-check

        for dirpath, dirnames, filenames in os.walk(os.environ['NZBPP_DIRECTORY']):
            for file in filenames:
                fileExtension = os.path.splitext(file)[1]

                if fileExtension in ['.par2']:
                    print "[INFO] Post-Process: Unpack skipped and par-check skipped (although par2-files exist), setting status \"failed\"g"
                    status = 1
                    break

        if os.path.isfile(os.path.join(os.environ['NZBPP_DIRECTORY'], "_brokenlog.txt")) and not status == 1:
            print "[INFO] Post-Process: _brokenlog.txt exists, download is probably damaged, exiting"
            status = 1

        if not status == 1:
            print "[INFO] Neither par2-files found, _brokenlog.txt doesn't exist, considering download successful"

    # Check if destination directory exists (important for reprocessing of history items)
    if not os.path.isdir(os.environ['NZBPP_DIRECTORY']):
        print "[INFO] Post-Process: Nothing to post-process: destination directory ", os.environ['NZBPP_DIRECTORY'], "doesn't exist"
        status = 1

    # All checks done, now launching the script.

    unpackExtensions = [x.strip() for x in os.environ['NZBPO_UNPACKEXTENSIONS'].split(',')]
    ec = sys.stdout.encoding
    unpacked = False
    for dirpath, dirnames, filenames in os.walk(os.environ['NZBPP_DIRECTORY']):
        for file in filenames:

            filePath = os.path.join(dirpath, file)
            fileName, fileExtension = os.path.splitext(file)

            if fileExtension in unpackExtensions:  # If the file is a rar file
                if not is_small(filePath, os.environ['NZBPP_NZBNAME'], os.environ['NZBPO_MINSIZE']):
                    print "[INFO] unpacking file: ", filePath
                    sys.stdout.flush()
                    try:
                        if fileExtension == ".rar":
                            part_r = re.search(r"part(\d+)$",fileName, re.IGNORECASE)
                            if (part_r is not None) and (int(part_r.group(1)) != 1):
                                continue
                            proc = subprocess.Popen(["unrar", "x", "-y", "-o+", "-p-", os.path.normpath(filePath), os.path.normpath(dirpath)], stdout=subprocess.PIPE)
                        elif fileExtension == ".zip":
                            proc = subprocess.Popen(["unzip", "-o", os.path.normpath(filePath), "-d" , os.path.normpath(dirpath)], stdout=subprocess.PIPE)
                        elif fileExtension == ".7z":
                            proc = subprocess.Popen(["7z", "x", "-y", os.path.normpath(filePath), '-o' + os.path.normpath(dirpath)], stdout=subprocess.PIPE)
                        ok = False
                        rar_files = []
                        for line in iter(proc.stdout.readline,''):
                            if line != None:
                                if ec != None:
                                    lin = line.decode(ec).rstrip()
                                else:
                                    lin = line.rstrip()
                                if (re.search("^Extracting from (.+)",lin,re.IGNORECASE|re.MULTILINE) != None):
                                    rar_files.append(re.search("^Extracting from (.+)",lin,re.IGNORECASE|re.MULTILINE).group(1))
                                if (re.search("^All OK$",lin,re.IGNORECASE|re.MULTILINE) != None) or (re.search("^Everything is Ok$",lin,re.IGNORECASE|re.MULTILINE) != None):
                                    ok = True
                                if len(lin.strip()) > 0:
                                    print "[INFO]", lin.strip()
                                    sys.stdout.flush()
                        proc.poll()
                        print "[INFO] unpack return code: ", str(proc.returncode)
                        if ok or ((fileExtension == ".zip" or fileExtension == ".7z") and proc.returncode == 0):
                            unpacked = True
                            time.sleep(3)
                            try:
                                os.unlink(os.path.normpath(filePath))
                                print "[INFO] unpacked and deleted: ", filePath
                            except:
                                print "[ERROR] could not delete: ", filePath
                            sys.stdout.flush()
                            if len(rar_files) > 0:
                                for r_file in rar_files:
                                    if os.path.isfile(os.path.normpath(os.path.join(dirpath,r_file))):
                                        try:
                                            os.unlink(os.path.normpath(os.path.join(dirpath,r_file)))
                                            print "[INFO] unpacked and deleted: ", os.path.normpath(os.path.join(dirpath,r_file))
                                        except:
                                            print "[ERROR] could not delete: ", r_file
                                        sys.stdout.flush()
                    except Exception,e:
                        print "[INFO] " + str(e)
                        print "[INFO] Error: unable to unpack file", filePath
                    sys.stdout.flush()
    if unpacked:
        sys.exit(POSTPROCESS_SUCCESS)
    else:
        sys.exit(POSTPROCESS_NONE)

else:
    print "[ERROR] This script can only be called from NZBGet (11.0 or later)."
    sys.exit(0)
