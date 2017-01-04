#!/usr/bin/python
#
# Citrix XenServer Patcher
version = "1.5.2"
# -- Designed to automatically review available patches from Citrix's XML API,
#    compare with already installed patches, and apply as necessary- prompting the user
#    to reboot/restart the XE ToolStack if necessary.
#
# Written by: Darren Gibbard
# URL:        http://dgunix.com
# Github:     http://github.com/dalgibbard/citrix_xenserver_patcher
#
#
# Written for Python 2.4 which is present in current XenServer 6.1/6.2+ Builds, but also somewhat
# tested against Python2.7 and 3.2 where possible for future compatibility.
#
# LICENSE:
# This code is governed by The WTFPL (Do What the F**k You Want to Public License).
# Do whatever you like, but I would of course appreciate it if you fork this code and commit back
# with any good updates though :)
#
# DISCLAIMER:
# Both myself and this code are in no way affiliated with Citrix. This code is not supported by Citrix in any way.
# Use of the code within this project is without warranty, and neither myself, the company I work for, nor other contributors of this project are to blame for any issues which may arise, and therefore cannot be held accountable.
# Any use of this code is done so at your own risk.

############################
### IMPORT MODULES START ###
############################
import sys, re, subprocess, os, getopt, time, pprint, signal, base64, cookielib, urllib2, urllib
from xml.dom import minidom
from operator import itemgetter
try:
    # Python v2
    from urllib2 import urlopen
except ImportError:
    # Python v3
    from urllib.request import urlopen
############################
### IMPORT MODULES END ###
############################

###############################
### INITIAL FUNCTIONS START ###
###############################
### Capture Ctrl+C Presses
def signal_handler(signal, frame):
    print("Quitting.\n")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

### Check if the host is the PoolMaster
def is_master():
    xensource = '/etc/xensource/pool.conf'
    f = open(xensource, 'r')
    if f.read() == 'master':
        return True
    return False
#############################
### INITIAL FUNCTIONS END ###
#############################

############################
### USER VARIABLES START ###
############################
# Where we can find the XML page of available updates from Citrix
patchxmlurl = 'http://updates.xensource.com/XenServer/updates.xml'
# Where we can find auto-exclude files on the internet - filename expected is either:
## "XS${majver}${minver}${subver}_exclusions.py"   - ie. "XS621_excludes.py" for XenServer 6.2.1
## "XS${majver}${minver}_exclusions.py"            - ie. "XS62_excludes.py" for XenServer 6.2.1 (if the above doesn't exist) OR XenServer 6.2
autourl = 'https://raw.githubusercontent.com/dalgibbard/citrix_xenserver_patcher/master/exclusions'
# Where we can store some temporary data
tmpfile = '/var/tmp/xml.tmp'
# Citrix Login credentials
cuser = ''
cpass = ''

##########################
### USER VARIABLES END ###
##########################

########################################
### SYSTEM / INITIAL VARIABLES START ###
########################################
# Setup empty List for later
L = []
# Specify empty excludes file -- when specified, this is a list of patches to IGNORE [opt: -e FILENAME ]
exclude_file = False
exclusions = False
autoexclusions = False
# Define "auto" as False by default -- when true, apply patches without question. [opt: -a ]
auto = False
# Define "reboot" as False by default. -- when true, if patches installed require host reboot, this will be done automatically!
autoreboot = False
# Define "listonly" as False by Default -- when true, list patches needed, but quit straight after. [opt: -l ]
listonly = False
# Define "pool" as False by Default -- when true, patches are applied to a pool
pool = False
# Enable loading of the Auto-Excludes list from github.
autoExclude = True
# A var used during the patch apply stage, when it gets set to non-zero if a patch recommends a reboot.
reboot = 0
# Disable debug by default
debug = False
# Clean out installed patches by default
clean = True
# Citrix Login URLs
citrix_login_url = 'https://www.citrix.com/login/bridge?url=https%3A%2F%2Fsupport.citrix.com%2Farticle%2FCTX219378'
citrix_err_url = 'https://www.citrix.com/login?url=https%3A%2F%2Fsupport.citrix.com%2Farticle%2FCTX219378&err=y'
citrix_authentication_url = 'https://identity.citrix.com/Utility/STS/Sign-In'
######################################
### SYSTEM / INITIAL VARIABLES END ###
######################################

#######################################
### USAGE + ARGUMENT HANDLING START ###
#######################################
## Define usage text
def usage(exval=1):
    print("Usage: %s [-p] [-e /path/to/exclude_file] [-E] [-a] [-r] [-l] [-U <username>] [-P <password>] [-D] [-C] [-v]" % sys.argv[0])
    print("")
    print("-p                          => POOL MODE: Apply Patches to the whole Pool. It must be done on the Pool Master.")
    print("-e /path/to/exclude_file    => Allows user to define a Python List of Patches NOT to install.")
    print("-E                          => *Disable* the loading of auto-exclusions list from Github")
    print("-a                          => Enables auto-apply of patches - will NOT reboot host without below option.")
    print("-r                          => Enables automatic reboot of Host on completion of patching without prompts.")
    print("-l                          => Just list available patches, and Exit. Cannot be used with '-a' or '-r'.")
    print("-D                          => Enable DEBUG output")
    print("-U <username>               => Citrix account username")
    print("-P <password>               => Citrix account password")
    print("-C                          => *Disable* the automatic cleaning of patches on success.")
    print("-v                          => Display Version and Exit.")
    print("-h                          => Display this message and Exit.")
    sys.exit(exval)


# Parse Args:
try:
    myopts, args = getopt.getopt(sys.argv[1:],"vhpe:EalrUPDC")
except getopt.GetoptError:
    usage()

for o, a in myopts:
    if o == '-v':
        # Version print and Quit.
        print("Citrix_XenServer_Patcher_Version: " + str(version))
        sys.exit(0)
    if o == '-h':
        # Version print and Quit.
        usage(0)
    elif o == '-e':
        # Set the exclusion file
        exclude_file = str(a)
        # Check the file exists
        if not os.path.exists(exclude_file):
            # If it doesn't exist, Error and quit.
            print("Failed to locate requested excludes file: " + exclude_file)
            sys.exit(1)
        # Our exclusions list is raw python, so try running it.
        try:
            execfile(exclude_file)
        # If running it fails, it's not valid python
        except Exception, err:
            print("An error occurred whilst loading the exclude file: " + exclude_file)
            if debug == True:
                print("Error: " + str(err))
            sys.exit(1)
        # Check that the Python we just ran actually contains some valid exclusions!
        if exclusions == False:
            print("No exclusions found in the loaded exceptions file...")
            sys.exit(1)
    elif o == '-p':
        # With 'pool-mode' enabled, check if we're the Master node.
        if is_master():
            pool = True
        # If we're not the Pool Master, Error and quit.
        else:
            print("The option -p must be used on a pool master.")
            sys.exit(1)
    elif o == '-E':
        # Disable Auto-Exclusions list
        autoExclude = False
    elif o == '-a':
        # Set Auto-mode to enabled. This will hide user prompts.
        auto = True
        # Check that 'listonly' hasn't been set also, as this is an invalid combination.
        if listonly == True:
            print("Cannot use 'list' with 'auto' or 'autoreboot' arguments.")
            print("")
            usage()
    elif o == '-r':
        # Set auto-reboot to enabled.
        autoreboot = True
        # Check that 'listonly' hasn't been set also, as this is an invalid combination.
        if listonly == True:
            print("Cannot use 'list' with 'auto' or 'autoreboot' arguments.")
            print("")
            usage()
    elif o == '-l':
        listonly = True
        if auto == True or autoreboot == True:
            print("Cannot use 'list' with 'auto' or 'autoreboot' arguments.")
            print("")
            usage()
    elif o == '-U':
        # Set citrix user
        cuser = str(a)
    elif o == '-P':
        # set citrix pass
        cpass = str(a)
    elif o == '-C':
        clean = False
    elif o == '-D':
	    debug = True
    else:
        usage()
#####################################
### USAGE + ARGUMENT HANDLING END ###
#####################################

if debug == True:
    print("Citrix_XenServer_Patcher_Version: " + str(version))

##############################
### SCRIPT FUNCTIONS START ###
##############################
def listappend(name_label, patch_url, uuid, name_description="None", after_apply_guidance="None", timestamp="0", url="None"):
    ''' Function for placing collected/parsed Patch File information into a dictionary, and then into a List '''
    dict = { "name_label": name_label, "name_description": name_description, "patch_url": patch_url, "uuid": uuid, "after_apply_guidance": after_apply_guidance, "timestamp": timestamp, "url": url }
    if debug == True:
	    print("Adding patch to list: " + str(dict))
    L.append(dict)

def listremovedupe(uuid):
    ''' Function to compare the list formed by the function above, to see if a passed patch UUID already exists; and
        if it does, remove it from the list (as it's already installed.) '''
    try:
        # Python v2
        patch_to_remove = (patch for patch in L if patch["uuid"] == uuid ).next()
    except AttributeError:
        # Python v3
        patch_to_remove = next((patch for patch in L if patch["uuid"] == uuid ), None)
    except StopIteration:
        pass
    try:
        L.remove(patch_to_remove)
    except UnboundLocalError:
        pass

def listremoveexclude(namelabel):
    ''' Similar to above function - but this will remove items from the "to_be_installed" list based on name-label
        instead of UUID. '''
    try:
        # Python v2
        patch_to_remove = (patch for patch in L if patch["name_label"] == namelabel ).next()
    except AttributeError:
        # Python v3
        patch_to_remove = next((patch for patch in L if patch["name_label"] == namelabel ), None)
    except StopIteration:
        pass
    try:
        L.remove(patch_to_remove)
    except UnboundLocalError:
        pass
    

def which(program):
    ''' Function for establishing if a particular executable is available in the System Path; returns full
        exec path+name on success, or None on fail. '''
    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            path = path.strip('"')
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file

    return None

def login():
    print("")
    print("Logging in")
    # Store the cookies and create an opener that will hold them
    cj = cookielib.CookieJar()
    opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj))

    # Add our headers
    opener.addheaders = [('User-agent', 'XenPatch')]

    # Install our opener (note that this changes the global opener to the one
    # we just made, but you can also just call opener.open() if you want)
    urllib2.install_opener(opener)

    # Input parameters we are going to send
    payload = {
      'returnURL'  : citrix_login_url,
      'errorURL'   : citrix_err_url,
      'persistent' : '1',
      'username'   : cuser,
      'password'   : cpass
      }

    # Use urllib to encode the payload
    data = urllib.urlencode(payload)

    # Build our Request object (supplying 'data' makes it a POST)
    req = urllib2.Request(citrix_authentication_url, data)
    try:
        u = urllib2.urlopen(req)
	contents = u.read()
    except Exception, err:
        print("...ERR: Failed to Login!")
        print("Error: " + str(err))
        sys.exit(3)

def download_patch(patch_url):
    url = patch_url
    file_name = url.split('/')[-1]
    print("")
    print("Downloading: " + str(file_name))
    try:
        u = urlopen(url)
    except Exception, err:
        print("...ERR: Failed to Download Patch!")
        print("Error: " + str(err))
        sys.exit(3)
        
    try:
        f = open(file_name, 'wb')
    except IOError:
        print("Failed to open/write to " + file_name)
        sys.exit(2)

    meta = u.info()
    try:
        file_size = int(meta.getheaders("Content-Length")[0])
        size_ok = True
    except IndexError, err:
        print("...WARN: Failed to get download size from: %s" % patch_url)
        print("         Will attempt to continue download, with unknown file size")
        time.sleep(4)
	###############
        size_ok = False

    # Check available disk space
    s = os.statvfs('.')
    freebytes = s.f_bsize * s.f_bavail
    if size_ok == False:
        doublesize = 2048
        file_size = 1
    else:
        doublesize = file_size * 2
    if long(doublesize) > long(freebytes):
        print(str("Insufficient storage space for Patch ") + str(file_name))
        print(str("Please free up some space, and run the patcher again."))
        print("")
        print(str("Minimum space required: ") + str(doublesize))
        sys.exit(20)

    print "Download Size: %s Bytes" % (file_size)
        
    file_size_dl = 0
    block_sz = 8192
    while True:
        buffer = u.read(block_sz)
        if not buffer:
            break
        file_size_dl += len(buffer)
        f.write(buffer)
        if size_ok == False:
             status = r"%10d" % (file_size_dl)
        else:
             status = r"%10d  [%3.2f%%]" % (file_size_dl, file_size_dl * 100. / file_size)
        status = status + chr(8)*(len(status)+1)
        print status,
    f.close()
    if not os.path.isfile(file_name):
        print("\nERROR: File download for " + str(file_name) + " unsuccessful.")
        sys.exit(15)
    return file_name

def apply_patch(name_label, uuid, file_name, host_uuid):
    print("\nApplying: " + str(name_label))
    print("Uncompressing...")
    patch_unzip_cmd = str("unzip -u ") + str(file_name)
    ### Ready for patch extract
    out = None
    err = None
    do_patch_unzip = subprocess.Popen([patch_unzip_cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    (out, err) = do_patch_unzip.communicate()
    if (err and out != None ):
        print("Error extracting compressed patchfile: " + str(file_name))
    if clean == True:
        os.remove(file_name)
    uncompfile = str(name_label) + str(".xsupdate")
    # Check {name_label}.xsupdate exists
    if not os.path.isfile(uncompfile):
        print("Failed to locate unzipped patchfile: " + str(uncompfile))
        sys.exit(16)
    # Internal upload to XS patcher
    print("Internal Upload...")
    patch_upload_cmd = str(xecli) + str(" patch-upload file-name=") + str(uncompfile)
    do_patch_upload = subprocess.Popen([patch_upload_cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    # On Python 2.4 check_* functions have not been yet implemented. Lets wait until Popen completes and read out the return code
    do_patch_upload.wait()
    (out, err) = do_patch_upload.communicate()
    # Upload may fail if file has previously already been uploaded but not applied
    if (err):
        print("XE Error detected: " + err)
        print("Return code is: " + str(do_patch_upload.returncode))
        error_block = err.split('\n')
        if (do_patch_upload.returncode == 1 and error_block[0] == "The uploaded patch file already exists"):
            print("Patch previously uploaded, attempting to reapply " + str(uuid))
        else:        
            print("New error detected, aborting")
            sys.exit(123)
    else:
        # Second verification.
        out = None
        err = None
        patch_upload_uuid = None
        #Do not pass hostuuid here as the patch has not been applied yet and the patch-list for SRO will come back empty
        patch_upload_verify_cmd = str(xecli) + str(' patch-list params=uuid uuid=') + str(uuid) + str(" --minimal")
        do_patch_upload_verify = subprocess.Popen([patch_upload_verify_cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        (out, err) = do_patch_upload_verify.communicate()
    
        if (err):
            print("Failed to validate the uploaded patch: " + str(uncompfile) + "\nError: " + str(err))
            sys.exit(17)
        else:
            print("Completed: " + str(out))

        patch_upload_uuid_utf8 = out.decode("utf8")
        patch_upload_uuid = str(patch_upload_uuid_utf8.replace('\n', ''))
        patch_upload_uuid.rstrip('\r\n')
        if not ( patch_upload_uuid != None and patch_upload_uuid == uuid ):
            print("Patch internal upload failed for: " + str(uncompfile))
            print("patch_upload_uuid = " + str(patch_upload_uuid))
            print("uuid = " + str(uuid))
            print("out = " + str(out))
            sys.exit(16)

    print("Applying Patch " + str(uuid))
    if pool == True:
        patch_apply_cmd = str(xecli) + str(" patch-pool-apply uuid=") + str(uuid)
    else:
        patch_apply_cmd = str(xecli) + str(" patch-apply uuid=") + str(uuid) + str(" host-uuid=") + str(host_uuid)
    if debug == True:
        print(str(patch_apply_cmd))
    do_patch_apply = subprocess.Popen([patch_apply_cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    (out, err) = do_patch_apply.communicate()
    if (err):
        print("Patch failed, code: " + str(do_patch_apply.returncode))
        print("Command failed: " + patch_apply_cmd)
        print("Failed to apply patch: " + str(err))
        print("Secondary validation check...")

    out = None
    err = None
    if pool == True:
        patch_apply_verify_cmd = str(xecli) + str(' patch-list ') + str(' params=uuid uuid=') + str(uuid) + str(" --minimal")
    else:
        patch_apply_verify_cmd = str(xecli) + str(' patch-list hosts:contains="') + str(host_uuid) + str('" params=uuid uuid=') + str(uuid) + str(" --minimal")

    do_patch_apply_verify = subprocess.Popen([patch_apply_verify_cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    (out, err) = do_patch_apply_verify.communicate()
    if (err):
        print("Failed to validate installed patch: " + str(uncompfile))
        sys.exit(18)
    patch_apply_uuid_utf8 = out.decode("utf8")
    patch_apply_uuid = str(patch_apply_uuid_utf8.replace('\n', ''))
    if not ( patch_apply_uuid != None and patch_apply_uuid == uuid ):
        print("Patch apply failed for: " + str(uncompfile))
        sys.exit(19)
        
    ## Cleanup
    if clean == True:
        if debug == True:
            print("Deleting file: " + uncompfile)
        try:
            os.remove(uncompfile)
        except OSError:
            print("Couldn't find file: " + uncompfile + " - Won't remove it.")
                    
        srcpkg_name = name_label + "-src-pkgs.tar.bz2"
        if debug == True:
            print("Deleting file: " + srcpkg_name)
        try:
            os.remove(srcpkg_name)
        except OSError:
            print("Couldn't find file: " + srcpkg_name + " - Won't remove it.")

        # Cleanup the /var/patch/ stuff using the XE Cli
        out = None
        err = None
        clean_var_cmd = str(xecli) + str(' patch-clean uuid=' + uuid)
        clean_var = subprocess.Popen([clean_var_cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        if debug == True:
            print("Running clean for Patch UUID " + uuid)
        (out, err) = clean_var.communicate()
        if not err:
            print("Cleaned patch data for UUID: " + uuid + "\n")
        else:
            print("Error encountered cleaning patch data for UUID: " + uuid)
            print("Error was: " + err + "\n")

    
## Function to pull Auto-Excludes file    
def getAutoExcludeList(autourl):
    # Build the full file URL:
    autourlfull = autourl + "/XS" + xsver + "_excludes.py"
            
    ### Start XML Grab + Parse
    try:
        # Get XML
        autoexclude_data = urlopen(autourlfull)
    except Exception, err:
        if not subver == "":
            print("Failed to locate Auto Exclusions file: XS" + xsver + "_excludes.py" )
            print("Checking for presence of Parent version file: XS" + majver + minver + "_excludes.py  ...")
            try:
                autourlfull = autourl + "/XS" + majver + minver + "_excludes.py"
                # Get XML
                autoexclude_data = urlopen(autourlfull)
            except Exception, err:
                # Handle Errors
                print("\nFailed to read Auto-Exclusion List from: " + autourlfull)
                print("Check the URL is available, and connectivity is OK.")
                print("")
                print("Error: " + str(err))
                print("")
                print('NOTE: To proceed without downloading the Auto-Excludes file (not recommended), pass the "-E" flag.')
                sys.exit(1)
        else:
            # Handle Errors
            print("\nFailed to read Auto-Exclusion List from: " + autourlfull)
            print("Check the URL is available, and connectivity is OK.")
            print("")
            print("Error: " + str(err))
            print("")
            print('NOTE: To proceed without downloading the Auto-Excludes file (not recommended), pass the "-E" flag.')
            sys.exit(1)

    # Set "autoexclude" to readable/printable page content.
    autoexclude = autoexclude_data.read()
    
    # Our exclusions list is raw python, so try running it.
    try:
        exec autoexclude
    # If running it fails, it's not valid python
    except Exception:
        print("An error occurred whilst loading the auto-exclude file from " + autourlfull)
        sys.exit(1)
    # Check that the Python we just ran actually contains some valid exclusions!
    if autoexclusions == False:
        print("No auto-exclusions found in the loaded exceptions file...")
        sys.exit(1)
    else:
	    return autoexclusions
            
# Function to test that the xe utility is operational (#21)
def xetest():
    out = None
    err = None
    test_xe_cmd = str(xecli) + str(' host-list')
    test_xe = subprocess.Popen([test_xe_cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    if debug == True:
        print("Testing XE CLI function using: " + test_xe_cmd)
    (out, err) = test_xe.communicate()
    if not err and out != None:
        return True
    else:
        return False
    
# Function for restarting XE Toolstack
def xetoolstack_restart():
    out = None
    err = None
    xe_restart_cmd = str(xecli) + str('-toolstack-restart')
    xe_restart = subprocess.Popen([xe_restart_cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    if debug == True:
        print("Restarting the XE Toolstack using: " + xe_restart_cmd)
    (out, err) = xe_restart.communicate()
    if not err and out != None:
        return True
    else:
        return False

# Define a function for unmounting all CDs
def unmount_cd():
    print("\n\nUnmounting CD Images from VMs...\n")
    out = None
    err = None
    cd_unmount_cmd = str(xecli) + str(' vm-cd-eject --multiple')
    do_cd_unmount = subprocess.Popen([cd_unmount_cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    (out, err) = do_cd_unmount.communicate()
    if (err):
        print("")
        print("An error occurred when attempting to unmount the CD Images:")
        print('"' + str(err) + '"')
        print("\n** NOTE: ** Errors due to non-CDROM devices, or Empty drives can be ignored.")
        if auto == True:
            print("\nAttempting auto-upgrade anyway in 10s - press Ctrl+C to abort...")
            time.sleep(10)
        else:
            cdans = raw_input("\nWould you like to continue anyway? [y/n]: ")
            if str(cdans) == "y" or str(cdans) == "yes" or str(cdans) == "Yes" or str(cdans) == "Y" or str(cdans) == "YES":
                print("Continuing...")
            else:
                print("Please manually unmount (or fix the reported issues), and run the patcher again.")
                sys.exit(112)            
############################
### SCRIPT FUNCTIONS END ###
############################

#######################    
### MAIN CODE START ###
#######################
# Validate that we're running XenServer
relver = '/etc/xensource-inventory'
xs = False
xsver = None

# Open Filehandle to relver to check version
try:
    f = open(relver, "r")
    # If this file is openable, we can safely assume that it's a XenServer box
    xs = True
except IOError:
    print("Error Opening " + relver)
    try:
        f.close()
    except NameError:
        pass
    sys.exit(11)

# Read the relver contents, and split into variables for the XenServer version.
shortver = None
try:
    for line in f:
        if re.search("PRODUCT_VERSION=", line):
            shortver = line.split("=")[1].replace("'", "")
    if shortver == None:
        print("Failed to identify Major/Minor XenServer Version.")
        sys.exit(23)
    else:
        print("Detected XenServer Version: " + shortver)
    majver = shortver.split('.')[0]
    minver = shortver.split('.')[1]
    # Provide 'xsver' for versions consisting of two and three segments. (eg: 6.2 vs 6.2.1)
    if len(shortver.split('.')) > 2:
        subver = shortver.split('.')[2].strip()
        if subver == '0':
	    subver = ""
            xsver = str(majver) + str(minver)
        else:
            xsver = str(majver) + str(minver) + str(subver)
    if debug == True:
        print("xsver: " + xsver)
finally:
    f.close()

# Check that relver listed 'XenServer' in it's contents.
if xs == False:
    print("Failed to identify this host as a XenServer box.")
    sys.exit(4)
elif debug == True:
    print("XenServer machine identified.")

# Ensure we found a valid XenServer Version.
if xsver == None:
    print("Failed to identify XenServer Version.")
    sys.exit(5)
elif debug == True:
    print("XenServer Version " + xsver + " detected.")

# Locate the 'xe' binary.
xecli = which("xe")
if xecli == None:
    print("Failed to locate the XE CLI Utility required for patching.")
    sys.exit(8)
elif debug == True:
    print("XE utility located OK")
    
# Now validate that XE is working:
if not xetest():
    print("XE CLI not responding. Calling 'xe-toolstack-restart':")
    if not xetoolstack_restart():
        print("Attempt to run xe-toolstack-restart failed. Quitting.")
        sys.exit(98)
    time.sleep(5)
    if not xetest():
        print("XE Still not responding. Quitting.")
        sys.exit(99)
    elif debug == True:
        print("XE restarted and responding OK.")
elif debug == True:
    print("XE working OK")
    
### Start XML Grab + Parse
try:
    # Get XML
    if debug == True:
        print("Downloading patch list XML")
    downloaded_data = urlopen(patchxmlurl)
except Exception, err:
    # Handle Errors
    print("\nFailed to read Citrix Patch List from: " + patchxmlurl)
    print("Check the URL is available, and connectivity is OK.")
    print("")
    print("Error: " + str(err))
    sys.exit(1)

# Set "data" to readable/printable page content.
data = downloaded_data.read()

#######################
# DEBUG - Show output #
#######################
if debug == True:
    print("-----------------------------")
    print("RAW XML OUTPUT:")
    print(data)
    print("-----------------------------")
#######################

# Output to tmpfile - Open file handle
try:
    t = open(tmpfile, "wb")
except IOError:
    print("Error Opening " + relver)
    try:
        t.close()
    except NameError:
        pass
    sys.exit(11)

# Output to tmpfile - Write Data + Close.
try:
    t.write(data)
finally:
    t.close()

if debug == True:
    print("XML written to " + tmpfile)    
    
# Parse XML to Vars
xmldoc = minidom.parse(tmpfile)
xmlpatches = xmldoc.getElementsByTagName('patch')

#Convert xsver to a string for use in regex
xsverstr = str(xsver)

### Parse Vars for each patch to a Dict, and add each Dict (PLUS) to the List
for s in xmlpatches:
    try:
        patchname = s.attributes['name-label'].value
    except KeyError:
        continue
    vermatch = "XS" + xsverstr
    if re.match(vermatch, patchname):
        # Set the name-label (Patch Filename)
        name_label = str(s.attributes['name-label'].value)
        # Set the patch-url (Where to download it from)
        patch_url = str(s.attributes['patch-url'].value)
        # Set the uuid (ID of the Patch)
        uuid = str(s.attributes['uuid'].value)
        # Set the name-description (What it fixes)
        name_description = str(s.attributes['name-description'].value)
        # Set the after-apply-guidance (What to do with the host once installed)
        try:
            after_apply_guidance = str(s.attributes['after-apply-guidance'].value)
        except KeyError:
            after_apply_guidance = None
        # Set the timestamp (when the patch was made available)
        try:
            timestamp = str(s.attributes['timestamp'].value)
        except KeyError:
            timestamp = None
        # Set the url (URL where Patch information can be found)
        try:
            url = str(s.attributes['url'].value)
        except KeyError:
            url = None
        
        # PUSH TO LIST
        listappend(name_label, patch_url, uuid, name_description, after_apply_guidance, timestamp, url)

## Validate that there is something defined in the Patch list... else quit.
if L == []:
    print("No Patches found on remote server for XS" + str(xsver))
    sys.exit(6)

# OK, so now we have a complete list of patches that Citrix have to offer. Lets see what we have installed already,
# and remove those from the list we made above.

# First, we use a subprocess shell to get the local host's XenServer UUID
out = None
err = None
get_host_uuid_cmd = str(xecli) + str(' host-list hostname=`grep "^HOSTNAME=" /etc/sysconfig/network | awk -F= \'{print$2}\'` params=uuid --minimal')
get_host_uuid = subprocess.Popen([get_host_uuid_cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
if debug == True:
    print("Getting host list using: " + get_host_uuid_cmd)
(out, err) = get_host_uuid.communicate()
if not err and out != None:
    HOSTUUID_utf8 = out.decode("utf8")
    HOSTUUID = str(HOSTUUID_utf8.replace('\n', ''))
    if debug == True:
        print("Detected HOST UUID: " + HOSTUUID)
else:
    print("Failed to get HostUUID from XE")
    sys.exit(7)

if HOSTUUID == "" or HOSTUUID == ['']:
    print("Error: Failed to obtain HOSTUUID from XE CLI")
    sys.exit(10)

# Setup empty list to use in a moment:
inst_patch_list = []

out = None
err = None
if pool == True:
    get_inst_patch_cmd = str(xecli) + str(' patch-list ') + str(' --minimal')
else:
    get_inst_patch_cmd = str(xecli) + str(' patch-list hosts:contains="') + str(HOSTUUID) + str('" --minimal')
get_inst_patch = subprocess.Popen([get_inst_patch_cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
if debug == True:
    print("Get patch list using: " + get_inst_patch_cmd)
(out, err) = get_inst_patch.communicate()
if not err and out != None:
    inst_patch_utf8 = out.decode("utf8")
    inst_patch_str = str(inst_patch_utf8.replace('\n', ''))
    inst_patch_list = inst_patch_str.split(",")
else:
    print("Failed to get Patch List from XE")
    sys.exit(9)

#############
### DEBUG ###
#############
if debug == True:
    print("HOSTUUID: " + HOSTUUID)
    print("Installed Patches: " + str(inst_patch_list))
#############


##### TEST DEBUG:
if debug == True:
    print("Trying to establish which 'null' is correct. If you see an 'X MATCHED' message, please notify me on Github via an Issue!")
    ## A
    if inst_patch_list == []:
        print(" *** A MATCHED *** ")
    ## B
    if inst_patch_list == "":
        print(" *** B MATCHED *** ")
    ## C
    if inst_patch_list == ['']:
        print(" *** C MATCHED *** ")
##### END TEST DEBUG
    
# If there's no patches installed on this machine yet, tell the user (in case they were curious)
if inst_patch_list == [] or inst_patch_list == "" or inst_patch_list == ['']:
    print("No Patches are currently installed.")
# Else; request that already installed patches are removed from the "to_be_installed" list:
else:
    for uuid in inst_patch_list:
        listremovedupe(uuid)
    
## Request, where necessary, that patches in the Exclusions file are removed.
if not exclusions == False:
    for namelabel in exclusions:
        listremoveexclude(namelabel)

if autoExclude:
    # Load the AutoExcludes:
    autoexclusions = getAutoExcludeList(autourl)

    ## Patches loaded in from the auto-exclude file to be removed from the list next:    
    if not autoexclusions == False:
        for namelabel in autoexclusions:
            listremoveexclude(namelabel)
        
## Lastly, sort the data by timestamp (to get oldest patches installed first).
sortedlist = sorted(L, key=itemgetter('timestamp'))

# Reassign the sorted list back to the old variable, 'cos I liked that one better.
L = sortedlist

# Dump the list to a temporary string for mangling into a readable output:
var = str(L)
# Do the mangling on the string to be human readable.
vara = var.replace(',','\n').replace('{','\n').replace('}','').replace('[','').replace(']','').replace("'", "")
# If we're done mangling, and the var is empty, then we have no patches to install.
if vara == "":
    print("No Patches Required. System is up to date.")
    sys.exit(0)

# If vara isn't empty, show the user a list of patches we're going to install.
print("The following Patches are pending installation:")
print(vara)

# If the user just wanted a list, quit now.
if listonly == True:
    sys.exit(0)

# If any of the patches in the list recommend a reboot after applying, increment the reboot var.
for a in L:
    if str(a['after_apply_guidance']) == "restartHost":
        reboot = reboot + 1

# If we find that one or more patches recommend a reboot, notify the user.
if reboot > 0:
    print("\nNOTE: Installation of these items will require a reboot!")
    if not autoreboot == True:
        print("      You will be prompted to reboot at the end.")
        print("")
    time.sleep(2)

# If auto isn't set, ask the user if they're ready to start applying patches.
if not auto == True:
    # Inserted a brief sleep, as debug output can lag in such a way that you don't see this prompt otherwise!
    time.sleep(2)
    ans = raw_input("\nWould you like to install these items? [y/n]: ")
    if str(ans) == "y" or str(ans) == "yes" or str(ans) == "Yes" or str(ans) == "Y" or str(ans) == "YES":
        print("")
    else:
        print("You didn't want to patch...")
        sys.exit(0)

# Check for mounted CDROMs and request unmount:
out = None
err = None
cd_check_cmd = str(xecli) + str(' vm-cd-list --multiple')
do_cd_check = subprocess.Popen([cd_check_cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
(out, err) = do_cd_check.communicate()
if (err):
    if not "No matching VMs found" in str(err):
        print(str("Failed to check for mounted CD Images- Error: ") + str(err))
        sys.exit(110)
if not out == "":
    if debug == True:
        print("CD Check Output: " + out)
    print("CD images are currently mounted to one or more VMs.")
    print("These must be unmounted before starting the patching process.")
    if auto == False:
        cd_ans = raw_input("\nWould you like to auto-umount these now? [y/n]: ")
        if str(cd_ans) == "y" or not str(cd_ans) == "yes" or str(cd_ans) == "Yes" or str(cd_ans) == "Y" or str(cd_ans) == "YES":
            unmount_cd()
        else:
            print("Please unmount manually before proceeding with patching.")
            sys.exit(111)
    else:
        unmount_cd()
    
# Now we're finally ready to actually start the patching!
print("Starting patching...")
# check for login 
if cuser and cpass:
    login()
# For each patch, run the apply_patch() function.
for a in L:
   uuid = str(a['uuid'])
   patch_url = str(a['patch_url'])
   name_label = str(a['name_label'])
   file_name = str(download_patch(patch_url))
   host_uuid = str(HOSTUUID)
   apply_patch(name_label, uuid, file_name, host_uuid)

# Now patching is completed, if a reboot was required (as noted earlier), tell the user now; unless they flagged autoreboot.
if reboot > 0:
    if not autoreboot == True:
        ans = raw_input("\nA reboot is now required. Would you like to reboot now? [y/n]: ")
        if str(ans) == "y" or str(ans) == "yes" or str(ans) == "Yes" or str(ans) == "Y" or str(ans) == "YES":
            print("Rebooting...")
            os.system("reboot")
        else:
            print("OK, i'll let you reboot in your own time. Don't forget though!")
    else:
        print("Rebooting...")
        os.system("reboot")
else:
    print("Restarting XAPI Toolstack...")
    xetoolstack_restart()

print("PATCHING COMPLETED")

