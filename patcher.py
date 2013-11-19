#!/usr/bin/python
#
# Written for Python 2.4 which is present in current XenServer 6.1/6.2+ Builds
#
# No real license here... Do whatever. I'd appreciate it if you fork this code and commit back
# with any good updates though :)
#


#def somethingfunc(applyguide=restartHost, name, description="No Description", url, timestamp=None, infourl=None, uuid):
#        self.applyguide = applyguide
#        self.
#    ''' This Class allows us to store, call and manage our Patch Files information. '''
 
### IMPORT MODULES
import urllib2, sys, re
from xml.dom import minidom
L = []

### USER VARS
# Where we can find the XML page of available updates from Citrix
patchxmlurl = 'http://updates.xensource.com/XenServer/updates.xml'
# Where we can store some temporary data
tmpfile = '/var/tmp/xml.tmp'
# Version to match against; 62 here means: 6.2
xsver = 62

### FUNCTIONS START
def listappend(name_label, patch_url, uuid, name_description="None", after_apply_guidance="None", timestamp="None", url="None"):
    dict = { "name_label": name_label, "name_description": name_description, "patch_url": patch_url, "uuid": uuid, "after_apply_guidance": after_apply_guidance, "timestamp": timestamp, "url": url }
    print("Printing dict:")
    print(dict)
    L.append(dict)

### CODE START
try:
    # Get XML
    downloaded_data = urllib2.urlopen(patchxmlurl)
except (urllib2.HTTPError, urllib2.URLError) as err:
    # Handle Errors
    print("Failed to read Citrix Patch List from: " + patchxmlurl)
    print("Check the URL is available, and connectivity is OK.")
    print("")
    print("Error: " + err)
    sys.exit(1)

# Set "data" to readable/printable page content.
data = downloaded_data.read()

# DEBUG - Show output
#print(data)

# Output to tmpfile
try:
    with open(tmpfile, "w") as myfile:
        myfile.write(data)
except IOError as err:
    print("Failed to write to tmpfile: " + tmpfile)
    print("Error: " + err)
    sys.exit(2)

# Parse XML to Vars
xmldoc = minidom.parse(tmpfile)
xmlpatches = xmldoc.getElementsByTagName('patch')

# DEBUG - Print found number of Items
print(len(xmlpatches))

# Initialise List

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
#    except KeyError as err:
#        print("KeyError hit: " + str(err))
#        pass
print("Here's the list...")
print(L)
## Just Patch Names:
#p = re.compile('name-label="XS') # + xsverstr + '[a-zA-Z0-9]"')
#m = p.match(data)
#print(m)
print("")
print("Exclude:")
exclude = str("XS62E005")
print(patch for patch in L if patch["name_label"] == exclude ).next()
