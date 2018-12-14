# Build & Boot CI
BBCI is a simple tool for building, booting and testing kernel.

## Usage:
```
./bbci.py -s source -t target -a action
```

You can separate source, target and actions by ","
You can also use all for source and target

Example:
build all source with all targets and boot them
```
./bbci.py -s all -t all -a build,boot
```

## Workflow
### build
./bbci.py -s source -t target -a build

### boot
./bbci.py -s source -t target -a boot

### Example

Testing linux-next with ARM devices
```
./bbci.py -s next -t arm_generic -a build
./bbci.py -s next -t arm_generic -a boot
```

Build linux-next targeting arm64:
```
./bbci.py -s next -t arm64_generic -a build
```
Then boot it
```
./bbci.py -s next -t arm64_generic -a boot
```

## External dependencies:
For using BBCI, you need the following:
* A LAVA instance
  	See https://wiki.linaro.org/LAVA
* A web server for hosting builded kernel
	The docroot need to be set in lab/datadir
* A collection of rootfs for all arches.
	Availlable via the lab/rootfs_baseuri parameter.

TODO: more documentation on buildroot and test


## Sources
```
sources:
  - name: 		(mandatory) Nickname of the sources
    directory:		(mandatory) Where are sources located
    gituri:		(optional)  The GIT URI for creating the repo
    update_script:	(optional)  the patch to a script which update the sources
    update_command:	(optional)  A command which update the sources (ex: git pull)
    tag:		(optional)  A tag option for update_script
```
Note:
* update_script and update_command and ran after a chdir on "directory".
* Furthermore update_script will be ran with directory as first argument and an optional "-T tag" if tag is set.

Example:
```
  - name: next
    directory: $HOME/linux-next
    gituri: https://git.kernel.org/pub/scm/linux/kernel/git/next/linux-next.git
    update_script: ./scripts/git-stable
    tag: next-
```
"./bbci.py -s next -a create" Will checkout linux-next in $HOME/linux-next
"./bbci.py -s next -a update" Will update linux-next in $HOME/linux-next

## Target triplet
Target triplet are arch/subarch/flavour:
* Arch need to be set to arch as used by Linux.
* Subarch are for either, SoC names for ARM/ARM64, 32/64 for others.
* Flavour are for having different kernel for the same arch/subarch

```
  - name: 		(mandatory) Name of the target
    larch:		(mandatory) Architecture as called by Linux
    cross_compile:	(mandatory) cross_compile prefix (or None)
    full_tgt:		(mandatory) make target to compile (Example: zImage modules)
    warnings:		(optional)  Flags for warning
    defconfig:		(optional)  A defconfig name to use
```

Examples:
* arm/bcm2835/default
* mips/mips64/malta
* arm64/a64/banapi
* arm64/a64/pine64

Note: If defconfig is not set, a .config must be already present in the final build directory.

## LAVA Lab
The labs entry describes a LAVA lab and how to interact with it.
```
labs:
  - name: 		(mandatory) Nickname of the LAB
    lavauri:		(mandatory) URI to access the LAVA LAB
    datadir:		(mandatory) Local directory where to copy data (kernel, dtb, modules) to use if bbCI is run on datahost
    datahost:		(mandatory) FQDN of the host storing data (kernel, dtb, modules)
    datahost_baseuri:	(mandatory) Base URI to access data (kernel, dtb, modules)
    rootfs_baseuri:	(mandatory) Base URI to access rootfs
```

## Device job template
```
  - name: unused
    arch: 		(mandatory)	Arch of the device
    larch: 		(optional)	Arch of the device as named by Linux (default to $arch)
    devicetype: 	(mandatory)	LAVA device type
    devicename: 	(optional)	Name displayed in LAVA jobs; default to devicetype
    kernelfile:		(mandatory)	kernel file used for booting (zImage, vmlinux, ...)
    mach:		(mandatory)	mach of device as used by kernelCI
    qemu:		(optional)	Specific informations for QEMU devices
        machine: 	(mandatory)	QEMU machine type
        memory: 		(optional)
        model: model=xx		(optional)	Network card
        guestfs_interface: 	(optional)	Interface for connecting the LAVA test storage
        extra_options:		(optional)	Options for this device, at least the console is needed (WiP console will be set as console:)
        - '-append "console=ttyS0 root=/dev/ram0"'
        - "-device ide-hd,drive=test"
    configs:			(optional) List of kernel configs needed/recommanded (WIP)
      - CONFIG_PCNET
      - CONFIG_RTC_CMOS
      - CONFIG_PIIX
    tags:			(optional)
      - ok
```

# WIP
## LAVA support
LAVA miss some part for booting all qemu and run tests properly.
patch will be sent upstream soon

## unbootable or problematic boards
### PPC
* taihu: uboot support removed 2/3 years ago
* virtex-ml507: Cannot do test due to missing storage
* 40p: Cannot boot it
* mpc8544ds: kernel crash, need to investigate
* ppce500: need -bios uboot
* ref405ep: TODO

### ARM
* sx1: Cannot boot it

### MIPS/MIPS64
* mips: Cannot boot it
* mipssim: Cannot boot it
* magnum: Need non-free firmware https://www.betaarchive.com/forum/viewtopic.php?f=62&t=6256
* pica61: Probably the same as magnum

### SPARC
* SS-10 and all other SS-XX: kernel crash with initrd (reported upstream, no answer yet)

### SPARC64
* niagara: need external firmware
* sun4v: expirimental, fail to boot
