# Build & Boot CI
BBCI is a simple tool for building, booting and testing kernel.

An extra goal is to have a reference of all possible QEMU machine bootable with Linux.

BBCI is licensed under the GPL-v2

## External dependencies:
For using BBCI, you need the following:
* A LAVA instance for booting devices/qemu
	See https://wiki.linaro.org/LAVA
* A web server for hosting builded kernel, since LAVA need to download them
	The docroot need to be set in lab/datadir
* A collection of rootfs for all arches.
	Availlable via the lab/rootfs_baseuri parameter.
* A toolchain for building. Note that BBCI could download one for you

## Usage:
```
./bbci.py -s source -t target -a action
```

You can separate source, target and actions by ","
You can also use all for source and target.
You can use defconfig for target for filtering only targets with defconfig: attribute.

Example:
build all source with all targets and boot them
```
./bbci.py -s all -t all -a build,boot
```

## Reference of all arguments
### --source/-s sourcename[,sourcename]
* One sourcename
* A list of sourcename separated by ","
* all
### --target/-t targetname[,targetname]
* Only one targetname
* A list of targetname separated by ","
* all
* defconfig
### --action/-a action[,action]
* download: download toolchain for specified targets
* build
* boot
* qemu
### --dtag/-D devicetag[,devicetag]
* A devicetag
* qemu: Select only qemu machines
### --ttag/-T sourcetag[;sourcetag]
### -W
Instead of exiting after ended the boot action (sending all jobs to LAVA server)
bbci will wait for all jobs to end
This is WIP.

### --debug -d
### --overlay -o overlayname[,overlayname]
See config overlay below

### --randconfigseed SEED
When using a randconfig target, use SEED as config seed.

## Quickstart
### build linux-next for x86
This is an example on how to test linux-next on x86 qemu.
This example assume you build on a X86 machine, see next example for cross compiling.
#### Checkout sources
```
./bbcy.py -s next -a create
```
This will checkout linux-next in the directory specified in

#### build linux-next for x86
```
./bbci.py -s next -t x86_defconfig -a build
```

#### boot the builded kernel on qemu
```
./bbci.py -s next -t x86_defconfig -a boot
```

### build a 4.20 linux-stable for ARM
This is an example on how to test the 4.20 stable Linux tree on ARM qemu.
#### Checkout sources
Add the following source section:
```
  - name: stable-4.20
    directory: $HOME/linux-stable-4.20
    gituri: https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git
    update_script: ./scripts/git-stable
    ltag: v4.20
```
Then do
```
./bbcy.py -s stable-4.20 -a create
```
This will checkout sources in $HOME/linux-stable-4.20

#### Verify and download cross compile toolchain
```
./bbcy.py -s stable-4.20 -t arm_defconfig -a download
```

#### build the stable sources
```
./bbci.py -s stable-4.20 -t arm_defconfig -a build
```

#### boot the builded kernel on qemu
```
./bbci.py -s stable-4.20 -t arm_defconfig -a boot
```

## Workflow
### build
```
./bbci.py -s source -t target -a build
```

### boot
```
./bbci.py -s source -t target -a boot
```

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


## config.yaml documentation
### config section
This section configure general bbci options
```
config:
    builddir: 	(mandatory) where to store build output
    toolchains: (mandatory) where to store downloaded toolchains
    cache:	(mandatory) where to store cached objects
```

### toolchains section
This section configure availlable toolchains
```
toolchains:
  - name:	(mandatory) Name of the toolchains
    larch:	(mandatory) The linux arch compilable by this toolchain
    url:	(optional)  Where to download this toolchain
    prefix:	(mandatory) The prefix of this toolchain
```

### Sources section
This section configure sources and where to store them
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

## all.yaml documentation
### Target triplet section
Target triplet are arch/subarch/flavour:
* Arch need to be set to arch as used by Linux.
* Subarch are for either, SoC names for ARM/ARM64, 32/64 for others.
* Flavour are for having different kernel for the same arch/subarch

```
targets:
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

### Config overlays
When building defconfig, sometime it miss some needed options.
Config overlays permit to tweak some configs after the defconfig generation
You can add configoverlays via the "-o". Multiple overlays can be specified, separated by ",".

```
configoverlays:
  - name: crypto
    list:
      - config: config to enable
      - config: config to disable
        disable: True
```
Example:
```
  - name: debug
    list:
      - config: CONFIG_DMA_API_DEBUG=y
      - config: CONFIG_DEBUG_INFO=y
      - config: CONFIG_DEBUG_KERNEL=y
```

The following config overlays are hardcoded:
* fulldebug:	Enable all debug options
* fullcrypto:	Enable all crypto options
* fulldrm:	Enable all DRM options
* fullsound:	Enable all sound options
* vanilla:	Disable all builtin changes
* nomodule:	Replace all CONFIG from modules to builtin

### Device job template
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

## labs.yaml
### LAVA Lab section
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


# TODO list
<ul>
<li>
rootfs selection: permit to use others rootfs
</li>
<li>
toolchain selection: currently it uses the first good one id find
</li>
<li>
toolchain cycling: like source/target
</li>
<li>
Implement a local qemu boot without LAVA
</li>
<li>
The cross_compile: None assume the host is x86, this is a wrong assumption.
bbci should detect the host arch.
</li>
<li>
Split all.yaml in config.yaml + many linuxarch.yaml
</li>
<li>
More arch
</li>
<li>
more documentation on buildroot and test
</li>
</ul>

# WIP
## More boot method
* change boot-method
* NBD
* NFS
* PXE

## QEMU status matrix
<table>
  <tr>
    <td rowspan="2">Arch</td>
    <td rowspan="2">board</td>
    <td rowspan="2">Boot</td>
    <td colspan="3">Tests</td>
  </tr>
  <tr>
    <td>HDD</td>
    <td>NFS</td>
    <td>NBD</td>
  </tr>
  <tr>
    <td>alpha</td>
    <td>clipper</td>
    <td>OK</td>
    <td>OK</td>
  </tr>
  <tr>
    <td rowspan="6">ARM</td>
    <td>Cubieboard</td>
    <td>OK</td>
    <td>OK</td>
  </tr>
  <tr>
    <td>Sabrelite</td>
    <td>OK</td>
    <td>OK</td>
  </tr>
  <tr>
    <td>virt</td>
    <td>OK</td>
    <td>OK</td>
  </tr>
  <tr>
    <td>vexpress-a9</td>
    <td>OK</td>
    <td>OK</td>
  </tr>
  <tr>
    <td>vexpress-a15</td>
    <td>OK</td>
    <td>OK</td>
  </tr>
  <tr>
    <td>imx-mcimx6ul-evk</td>
    <td>OK</td>
    <td>OK</td>
  </tr>
  <tr>
    <td>ARM64</td>
    <td>virt</td>
    <td>OK</td>
    <td>OK</td>
  </tr>
  <tr>
    <td>MIPS</td>
    <td>malta</td>
    <td>OK</td>
    <td>OK</td>
  </tr>
  <tr>
    <td>MIPS64</td>
    <td>malta</td>
    <td>OK</td>
    <td>OK</td>
  </tr>
  <tr>
    <td rowspan="6">PowerPC</td>
    <td>G3beige</td>
    <td>OK</td>
    <td>OK</td>
  </tr>
  <tr>
    <td>virtex-ml507</td>
    <td>OK</td>
    <td>KO</td>
  </tr>
  <tr>
    <td>Sam460ex</td>
    <td>OK</td>
  </tr>
  <tr>
    <td>mac99</td>
    <td>OK</td>
  </tr>
  <tr>
    <td>bamboo</td>
    <td>OK</td>
  </tr>
  <tr>
    <td>mpc8544ds</td>
    <td>OK</td>
  </tr>
  <tr>
    <td>PPC64</td>
    <td>pseries</td>
    <td>OK</td>
  </tr>
  <tr>
    <td>x86</td>
    <td>pc</td>
    <td>OK</td>
  </tr>
  <tr>
    <td>x86_64</td>
    <td>pc</td>
    <td>OK</td>
  </tr>
  <tr>
    <td>SPARC</td>
    <td>SS-10</td>
    <td>OK</td>
  </tr>
  <tr>
    <td>SPARC64</td>
    <td>sun4u</td>
    <td>OK</td>
  </tr>
</table>

## unbootable or problematic boards
### PPC
* taihu: uboot support removed 2/3 years ago
* 40p: Cannot boot it
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
* SS-10 and all other SS-XX: kernel crash with initrd (need to send fix to upstream)

### SPARC64
* niagara: need external firmware
* sun4v: experimental, fail to boot

### nios2
* No test (missing storage)

### xtensa
* boot stuck

### openrisc
* Not enough RAM for test
* Need initrd at buildtime
