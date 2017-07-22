# searchkconfig
searchkconfig is a tool that is intended to search kernel configuration trees
for a specific regex that occurs in either the help page or the option
description text. When an occurence is found, the whole menu tree to get there
is printed. This makes searching for a particular option nested deeply inside
the kernel configuration much easier. Furthermore, some options may be disabled
if certain dependencies are not met. searchkconfig parses the configuration
that is needed to show the specific options and offers printing the
prerequisite conditions that will allow you to select that particular option.

# Acknowledgments
searchkconfig uses the Toy Parser Generator (TPG) of Christophe Delord
(http://cdsoft.fr/tpg/). It is included (tpg.py file) and licensed under the
GNU LGPL v2.1 or any later version. 

# Usage
Usage is quite straightforward, see the help page:

<pre>
$ ./searchkconfig
Error: the following arguments are required: kernel_path

usage: searchkconfig [-h] [-a arch] [-n] [-s text] [-c path]
                     [--startfile path] [--include-unnamed] [--show-origin]
                     [--show-conditions] [--show-help] [--no-submenus]
                     kernel_path

positional arguments:
  kernel_path           Kernel source directory to scan

optional arguments:
  -h, --help            show this help message and exit
  -a arch, --arch arch  Source architecture, defaults to 'x86'.
  -n, --no-ignore-case  Honor case distinctions when searching.
  -s text, --search text
                        Search in help text and description text for a
                        particular regular expression and only display those
                        results.
  -c path, --kernel-config path
                        Filename of a kernel configuration that is
                        interpreted. Will give more insight on dependencies.
  --startfile path      Start file to open up, defaults to 'Kconfig'.
  --include-unnamed     Include unnamed options in output.
  --show-origin         Show origin (filename and line number) of the dumped
                        config options.
  --show-conditions     Print the preconditions that are required for that
                        option to be available.
  --show-help           Print the help pages of the dumped config options.
  --no-submenus         Do not convert 'menuconfig' options into submenus.
</pre>

Example:

<pre>
$ ./searchkconfig -a arm -s 'realtek.*8188' /usr/src/linux-4.12
Kconfig
    (l) Linux/$ARCH $KERNELVERSION Kernel Configuration
        (d) Device Drivers
            (e) Network device support (NETDEVICES)
                (w) Wireless LAN (WLAN)
                    (r) Realtek devices (WLAN_VENDOR_REALTEK)
                        (r) Realtek rtlwifi family of devices (RTL_CARDS)
                            (r) Realtek RTL8192CE/RTL8188CE Wireless Network Adapter (RTL8192CE)
                            (r) Realtek RTL8192DE/RTL8188DE PCIe Wireless Network Adapter (RTL8192DE)
                            (r) Realtek RTL8188EE Wireless Network Adapter (RTL8188EE)
                            (r) Realtek RTL8192CU/RTL8188CU USB Wireless Network Adapter (RTL8192CU)
            (s) Staging drivers (STAGING)
                (r) Realtek RTL8188EU Wireless LAN NIC driver (R8188EU)
                    (r) Realtek RTL8188EU AP mode (88EU_AP_MODE)
</pre>

# TODOs
Currently, the prerequisite expressions are parsed, but only symbols are
evaluated.  It would be relatively straightforward to also implement evaluation
of compound expressions.

# License
searchkconfig is licensed under the GNU GPL v3 (except for TPG, which comes
with its own license). Later versions of the GPL are explicitly excluded.

