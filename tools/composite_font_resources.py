"""Native TPC coverage, including the TXI embedded in each TPC payload."""
import struct
from PIL import Image

# Includes EXE suffix selection, high-DPI variants and GUI FONT fields.
FONT_ALIASES = (
    'dialogfont10x10', 'dialogfont10x10b', 'dialogfont16x16',
    'dialogfont16x16b', 'dialogfont32x32', 'dialogfont32x32b',
    'fnt_console', 'fnt_credits', 'fnt_creditsa', 'fnt_creditsb',
    'fnt_d10x10b', 'fnt_d16x16', 'fnt_d16x16b',
    'fnt_dialog16x16', 'fnt_galahad14',
    'd2xfnt_d16x16b', 'd3xfnt_d16x16b',
    'd2xfont16x16b', 'd3xfont16x16b',
    'diafnt16x16b_ps', 'd2xfont16x16b_ps', 'd3xfont16x16b_ps',
)

def make_tpc(tga, txi):
    """Uncompressed RGBA, one mip, bottom-up rows; no lossy DXT on dots.

    Layout agrees with OpenKotOR/PyKotor io_tpc.py: 128-byte header,
    encoding 4 with data_size=0, pixels, then ASCII TXI.
    """
    im = Image.open(tga).convert('RGBA')
    w, h = im.size
    pixels = im.transpose(Image.Transpose.FLIP_TOP_BOTTOM).tobytes()
    metadata = txi.read_text(encoding='ascii').strip().replace('\r\n', '\n')
    tail = (metadata.replace('\n', '\r\n') + '\r\n').encode('ascii') + b'\0'
    return struct.pack('<IfHHBB', 0, 0.0, w, h, 4, 1) + bytes(114) + pixels + tail

def verify_tpc(raw, tga, txi):
    size, alpha, w, h, encoding, mips = struct.unpack_from('<IfHHBB', raw)
    assert (size, alpha, encoding, mips) == (0, 0.0, 4, 1)
    image = Image.frombytes('RGBA', (w,h), raw[128:128+w*h*4])
    image = image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    original = Image.open(tga).convert('RGBA')
    assert image.size == original.size and image.tobytes() == original.tobytes()
    tail = raw[128+w*h*4:].rstrip(b'\0').decode('ascii').replace('\r\n', '\n').strip()
    assert tail == txi.read_text(encoding='ascii').replace('\r\n', '\n').strip()
    assert 'numchars 256' in tail
    assert all(len(name) <= 16 for name in FONT_ALIASES)
