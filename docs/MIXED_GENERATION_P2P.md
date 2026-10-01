# Mixed-Generation P2P (Turing + Ada, Ada + Blackwell, etc.)

Peer-to-peer GPU memory access between cards of different GPU generations is
supported by this repository via the `patch-libcuda-p2p.py` script. The script
patches `libcuda.so.1` to enable P2P where the stock driver rejects mixed-architecture
pairs (e.g., CMP 50HX on TU102/Turing + RTX 4070 on AD103/Ada).

The kernel-side patches (01–07) handle the PCIe link, ReBAR, and P2P enable/type
settings. The `libcuda.so.1` patch removes the architecture version check inside
the CUDA runtime library.

## Requirements

All three of these must be satisfied for P2P to work:

### 1. Above 4G Decoding + Resizable BAR

Both must be enabled in the BIOS/UEFI for **both** GPU slots. If the firmware
assigns too small a PCIe memory window, Linux cannot place a large BAR1.

### 2. IOMMU in passthrough mode

Use `iommu=pt` on the kernel command line. This makes all devices appear in a
single DMA domain so the GPUs can address each other directly.

```
intel_iommu=on iommu=pt
```

(On AMD: `amd_iommu=on iommu=pt`)

### 3. ACS disabled on PCIe root ports

ACS (Access Control Services) forces all P2P traffic through the CPU root complex,
reducing P2P bandwidth to ~2 GB/s. It must be disabled on the **root ports**, not
the GPUs themselves.

```
pci=realloc,hpmemsize=8G,hpmmiosize=256M,disable_acs_redir=<root_port_bdf>;...
```

**Important:** `disable_acs_redir` takes the BDF addresses of the **PCIe root
ports**, not the BDF of the GPU cards. The GPU BDF (e.g., `0000:08:00.0`) is the
downstream device and does not work here.

To find the root port BDFs:

```bash
# Show the PCIe tree — GPUs are leaf nodes, root ports are the switches/bridges
lspci -t

# Find the parent bridge of a specific GPU
lspci -PP | grep -B1 "0000:08:00.0"

# List all PCIe bridges to identify which are root ports
lspci -nn | grep -i "PCI bridge"
```

Example: If your GPUs are at `0000:08:00.0` and `0000:09:00.0`, the root port
they attach to might be `0000:04:08.0` (depends on your motherboard). Only that
root port's BDF goes into `disable_acs_redir`.

**Do not add `disable_acs_redir` blindly.** Use `lspci` to identify the root ports
manually first. If you disable ACS on the wrong device, your system may not boot
or may lose other PCI devices.

## Example kernel command line

```
intel_iommu=on iommu=pt pci=realloc,hpmemsize=8G,hpmmiosize=256M,disable_acs_redir=0000:04:08.0
```

## Verification

After rebooting, check that P2P is active:

```bash
# Check P2P read bandwidth between all GPUs
nvidia-smi topo -p2p r

# Check full topology matrix
nvidia-smi topo -m
```

If the matrix shows `SYS` instead of `PIX`, `PXB`, or `PHB` between GPUs, P2P is
not working. In that case:

- Verify IOMMU is in passthrough mode (`dmesg | grep -i iommu`)
- Verify ACS is disabled on the correct root ports (`lspci -s <root_port_bdf> -vvv | grep -i acs`)
- Verify both cards have large BARs enabled (`lspci -vvv | grep -A1 "Memory at"`)

Also run the CUDA P2P bandwidth test:

```bash
p2pBandwidthLatencyTest
```

All GPU pairs should print `CAN Access Peer Device`.
