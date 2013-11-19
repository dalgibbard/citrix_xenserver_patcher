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

### USER VARS
# Where we can find the XML page of available updates from Citrix
patchxmlurl = 'http://updates.xensource.com/XenServer/updates.xml'
# Where we can store some temporary data
tmpfile = '/var/tmp/xml.tmp'
# Version to match against; 62 here means: 6.2
xsver = 62

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

### Parse Vars for each patch to a Dict, and add each Dict (PLUS) to the List
# Initialise List
L = []

#Convert xsver to a string for use in regex
xsverstr = str(xsver)

for s in xmlpatches:
    try:
        patchname = s.attributes['name-label'].value
        vermatch = "XS" + xsverstr
        if re.match(vermatch, patchname):
            print(patchname)
    except KeyError:
        pass

## Just Patch Names:
#p = re.compile('name-label="XS') # + xsverstr + '[a-zA-Z0-9]"')
#m = p.match(data)
#print(m)
