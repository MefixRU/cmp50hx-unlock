# CMP 50HX P2P Enablement for 610.43.03

This patch set enables GPU-to-GPU transfers via PCIe BAR1 (Resizable BAR)
between the CMP 50HX (TU104, Turing) and other NVIDIA GPUs such as RTX 4070
(AD104, Ada Lovelace).

The CMP 50HX has a significantly enlarged BAR1 aperture compared to consumer
Turing cards (RTX 20 series), making it a viable target for BAR1-based P2P
even at 20 GB (up to 32 GB with the --rebar-32g flag).

## What This Does

The following patches enable P2P over BAR1 for the CMP 50HX:

- **06-cmp50-p2p-enable.patch**: Enables resizable BAR by default
  in both the kernel-open and nvalloc nv-reg.h headers.

- **07-cmp50-p2p-type.patch**: Forces the driver to use BAR1 for P2P
  rather than the default proprietary PCIe P2P protocol.

These patches are based on the open-source P2P implementation from
aikitoria/open-gpu-kernel-modules and adapted for the NVIDIA 610.43.03
open-gpu-kernel-modules source.

## Installation

Run the installer from within the cloned repository:

```bash
cd cmp50hx-unlock
sudo ./install.sh
```

For a 32 GB BAR1 (requires a motherboard/CPU that can place a large window):

```bash
cd cmp50hx-unlock
sudo ./install.sh --rebar-32g
```

For the optional idle P-state governor (drops idle power to ~2W):

```bash
cd cmp50hx-unlock
sudo ./install.sh --idle-governor
```

## IOMMU Configuration

BAR1 P2P requires IOMMU passthrough mode:

1. Edit `/etc/default/grub`
2. Add to `GRUB_CMDLINE_LINUX_DEFAULT`:
   - For AMD: `amd_iommu=on iommu=pt`
   - For Intel: `intel_iommu=on iommu=pt`
3. Run `sudo update-grub`
4. Reboot

## Verifying P2P

After installation and reboot, verify P2P connectivity using the
p2pBandwidthLatencyTest from the CUDA toolkit:

```bash
# Run from within a CUDA toolkit installation
/path/to/samples/5_Devices/p2pBandwidthLatencyTest/p2pBandwidthLatencyTest
```

You should see a connectivity matrix showing "1" (enabled) between all
GPUs.

## Notes

- The CMP 50HX must have Resizable BAR enabled in the motherboard BIOS/UEFI.
- The BAR1 size is limited by the host platform's ability to place a large
  memory window. On most desktop platforms, 16 GB is the practical limit.
- P2P bandwidth over PCIe Gen4 x16 is approximately 50-55 GB/s (unidirectional).
- The RTX 4070 and CMP 50HX will use different PCIe lanes, so ensure your
  motherboard has sufficient PCIe lanes for both cards.
