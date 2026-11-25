#!/usr/bin/env python3
"""Package the Aule USB and OTA images separately; never OTA a full flash image."""

import argparse
import hashlib
import re
import struct
from pathlib import Path

from publish_firmware import firmware_metadata


def package(build_dir, output, version):
    if not re.fullmatch(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", version):
        raise ValueError("Expected a numeric release version")
    merged = (build_dir / "merged-binary.bin").read_bytes()
    app = (build_dir / "xiaozhi.bin").read_bytes()
    meta = firmware_metadata(merged)
    if meta["version"] != version or meta["chip_id"] != 9 or meta["project"] != "xiaozhi":
        raise ValueError("Expected this version of the ESP32-S3 application")
    if len(app) < 288 or app[0] != 0xE9 or struct.unpack_from("<I", app, 32)[0] != 0xABCD5432:
        raise ValueError("OTA requires an application image, not a merged flash image")
    for pos in range(0x8000, 0x9000, 32):
        if merged[pos:pos + 3] == b"\xaa\x50\x00":
            offset, capacity = struct.unpack_from("<II", merged, pos + 4)
            if len(app) > capacity or merged[offset:offset + len(app)] != app:
                raise ValueError("OTA image must match the application in the USB image and fit its slot")
            break
    output.mkdir(parents=True, exist_ok=False)
    sums = []
    for suffix, data in ((".bin", merged), (".ota.bin", app)):
        name = f"aule-v0.2-{version}{suffix}"
        (output / name).write_bytes(data)
        sums.append(f"{hashlib.sha256(data).hexdigest()}  {name}\n")
    (output / "SHA256SUMS").write_text("".join(sums), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", type=Path, default=Path("build"))
    parser.add_argument("--output", type=Path, default=Path("release"))
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    package(args.build_dir, args.output, args.version)
