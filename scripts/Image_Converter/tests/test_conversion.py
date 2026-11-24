"""Exercise the converter's real Pillow path without opening a GUI window."""

import contextlib
import io
from pathlib import Path
import re
import struct
import sys
import tempfile
import tkinter
import unittest

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lvgl_tools_gui import CompressMethod, ImageConverterApp


class ImageConverterTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.output = self.directory / "output"
        self.output.mkdir()
        # Tcl variables work without a display; the image processing is unchanged.
        self.interpreter = tkinter.Tcl()
        self.app = ImageConverterApp.__new__(ImageConverterApp)
        self.app.output_dir = tkinter.StringVar(
            master=self.interpreter, value=str(self.output)
        )
        self.app.color_format = tkinter.StringVar(
            master=self.interpreter, value="自动识别"
        )

    def convert(self, image, *, filename="sample.png", size=(4, 3),
                compression=CompressMethod.NONE):
        source = self.directory / filename
        image.save(source)
        log = io.StringIO()
        with contextlib.redirect_stdout(log):
            self.app.convert_images([str(source)], *size, compression)
        basename = source.stem
        c_path = self.output / f"{basename}.c"
        png_path = self.output / f"{basename}_{size[0]}x{size[1]}.png"
        # The GUI catches exceptions, so a successful method return is not enough.
        self.assertTrue(c_path.is_file(), log.getvalue())
        self.assertTrue(png_path.is_file(), log.getvalue())
        with Image.open(png_path) as resized:
            self.assertEqual(resized.size, size)
            resized.load()
        c_source = c_path.read_text()
        self.assertIn(f".header.w = {size[0]}", c_source)
        self.assertIn(f".header.h = {size[1]}", c_source)
        data = re.search(r"uint8_t \w+_map\[\] = \{(.*?)\};", c_source, re.S)
        self.assertIsNotNone(data, c_source)
        payload = bytes(int(value, 16) for value in re.findall(r"0x([0-9a-f]{2})", data[1]))
        return c_source, payload

    def test_rgb_png_resizes_and_exports_rgb565(self):
        c_source, payload = self.convert(Image.new("RGB", (2, 2), (0, 255, 0)))
        self.assertIn("LV_COLOR_FORMAT_RGB565,", c_source)
        self.assertEqual(payload, bytes.fromhex("e0 07") * 12)

    def test_rgba_png_preserves_alpha_in_a_separate_plane(self):
        c_source, payload = self.convert(Image.new("RGBA", (2, 2), (255, 0, 0, 128)))
        self.assertIn("LV_COLOR_FORMAT_RGB565A8,", c_source)
        self.assertEqual(payload, bytes.fromhex("00 f8") * 12 + bytes([128]) * 12)

    def test_palette_png_transparency_is_detected(self):
        image = Image.new("P", (2, 2), 0)
        image.putpalette([255, 0, 0] + [0] * 765)
        image.info["transparency"] = 0
        c_source, payload = self.convert(image)
        self.assertIn("LV_COLOR_FORMAT_RGB565A8,", c_source)
        self.assertEqual(payload, bytes.fromhex("00 f8") * 12 + bytes(12))

    def test_jpeg_can_be_resized_and_exported(self):
        c_source, payload = self.convert(
            Image.new("RGB", (2, 2), (0, 255, 0)), filename="photo.jpg"
        )
        self.assertIn("LV_COLOR_FORMAT_RGB565,", c_source)
        self.assertEqual(len(payload), 4 * 3 * 2)

    def test_rle_output_has_a_valid_header_and_pixel_run(self):
        c_source, payload = self.convert(
            Image.new("RGB", (2, 2), (0, 255, 0)),
            size=(16, 2),
            compression=CompressMethod.RLE,
        )
        self.assertIn("LV_IMAGE_FLAGS_COMPRESSED", c_source)
        # LVGL RLE: method, compressed length, raw length, run count, RGB565 pixel.
        self.assertEqual(payload, struct.pack("<III", 1, 3, 64) + bytes.fromhex("20 e0 07"))


if __name__ == "__main__":
    unittest.main()
