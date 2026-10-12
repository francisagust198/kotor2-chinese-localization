"""Current column16 font raster and encoder helpers; alternate transparent step 193."""
import argparse,collections,json,math,re
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from localization import ROOT,sha,write_json
from composite_font_resources import FONT_ALIASES,make_tpc,verify_tpc

GRID=16;STEP=128;FIRST=129;BACK=250;RESET=252;ADVANCE=249;SPACE=251
ALPHAS=(64,128,192,255);SIZE=1024;CELL=64;OVERLAY=32.5

def raster(c,font):
    # Shared 52px baseline in the 64px cell: preserve punctuation's natural
    # vertical position instead of moving every glyph's ink to the top.
    advance=font.getlength(c)
    canvas=Image.new('L',(64,64));draw=ImageDraw.Draw(canvas)
    if advance>64:
        wide=Image.new('L',(math.ceil(advance),64))
        ImageDraw.Draw(wide).text((0,-16),c,font=font,fill=255)
        canvas=wide.resize((64,64),Image.Resampling.LANCZOS)
    else:
        draw.text(((64-advance)/2,-16),c,font=font,fill=255)
    if c=='…':
        # Chinese ellipsis dots belong on the middle axis, not the Latin baseline.
        bounds=canvas.getbbox()
        if bounds:
            shifted=Image.new('L',canvas.size)
            shifted.paste(canvas,(0,32-(bounds[1]+bounds[3])//2))
            canvas=shifted
    return canvas.resize((GRID,GRID),Image.Resampling.LANCZOS)

def sequence(im):
    result=bytearray()
    for x in range(GRID):
        for y in range(GRID):
            value=im.getpixel((x,y));level=min(4,(value+32)//64)
            if level:result.extend((FIRST+y*4+level-1,BACK))
        result.append(STEP if x%2==0 else 193)
    result.extend((RESET,ADVANCE,32))
    return bytes(result)

def encode(text,mapping):
    out=bytearray()
    for chunk in re.split(r'(<[\x20-\x7e]+?>)',text):
        if chunk.startswith('<') and chunk.endswith('>') and chunk.isascii():out.extend(chunk.encode('ascii'));continue
        for c in chunk:
            if c==' ':out.extend((SPACE,32))
            elif ord(c)<128:out.append(ord(c))
            else:out.extend(mapping[c])
    return bytes(out)
