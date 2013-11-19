citrix_xenserver_patcher
========================

Auto / Manual Patching tool for Citrix XenServer Boxes
Keeping Python support for version 2.4 through to 3.2 at least. Should be highly compatible to reduce
future code changes!

## To-do:
* -Automatic detection of XS version-
* -Correct error capturing for XE CLI issues-
* PATCH DOWNLOAD AND INSTALL CODE!
* Manual run default; auto run available with "-a|--auto"
* "-r|--report" option for feeding back pending updates via Cron or whatever
* "-q|--quiet" option for no on-screen output. Exit codes will be very important therefore! (And the Documentation of..)
* Manual run gives list of outstanding patches with options; can pick any number of patches to apply :: Need to aggregate require post-install steps.
** Query user if they're ready to reboot/restart XAPI etc post-install..
