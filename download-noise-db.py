# The MIT License (MIT)
# Copyright (c) 2015 Microsoft Corporation
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import freesound
import string
import shutil
import unicodedata
import time
import glob
import os
import sys
import subprocess
import re


apiKey = ""  # 请填入你的 Freesound API 密钥

downloadAudio = True
delim = ",.?-_:;'\" ()[]{}&^%$#@!~`<>/|"


def shortstr(s, ds, l=0):
    for d in ds:
        s = s.replace(d, '').lower()
    return s if l == 0 else s[:l-1]


def remove_accents(input_str):
    nkfd_form = unicodedata.normalize('NFKD', input_str)
    return "".join(c for c in nkfd_form if not unicodedata.combining(c))


if len(sys.argv) != 2:
    print("Syntax: download-noise-db.py noise-db.txt")
    sys.exit(0)

soundList = sys.argv[1]
outDir = 'noise-samples'
os.makedirs(outDir, exist_ok=True)

c = freesound.FreesoundClient()
c.set_token(apiKey, "oauth2")

fileNo = 0
with open(soundList, 'r', encoding='utf-8') as f, \
     open('noise-file-list.txt', 'a', encoding='utf-8') as fnl, \
     open('noise-type-list.txt', 'a', encoding='utf-8') as fntl, \
     open(os.path.join(outDir, 'noise-db.txt'), 'a', encoding='utf-8') as fout if downloadAudio else None, \
     open(os.path.join(outDir, 'noise-db-fields.txt'), 'a', encoding='utf-8') as fr if downloadAudio else None:
    
    if downloadAudio and os.path.getsize(os.path.join(outDir, 'noise-db-fields.txt')) == 0:
        fr.write('noise-type sound-id username name duration src-audio-quality tgt-audio-quality tags\n')

    noisetypes = []
    for line in f:
        line = line.strip()
        s = line.split(' ')
        soundid, soundtag, soundlic = s[0], s[1], s[2]

        g = glob.glob(os.path.join(outDir, soundtag, f'{soundid}*.wav'))
        if g:
            print(f'skipping file {g[0]}')
            continue

        if soundtag not in noisetypes:
            noisetypes.append(soundtag)
            fntl.write(f'{soundtag}\n')
            fntl.flush()

        try:
            s = c.get_sound(soundid)
        except freesound.FreesoundException as e:
            if e.code == 400:
                continue
            if e.code == 429:
                print('maximum limit of requests to freesound reached (2000/day)')
                sys.exit(1)

        idxcr = s.description.find('\n')
        if idxcr >= 0:
            s.description = s.description[:idxcr]

        sdur = f"{s.duration:.0f}"
        ssrate = f"{s.samplerate / 1000:.1f}"
        sbrate = f"{s.bitrate / 1000:.1f}"

        sname = remove_accents(s.name.lower()).replace('.wav', '').replace('.mp3', '').replace('.aiff', '')
        sname = shortstr(sname, delim, 20)
        sname = ''.join(c for c in sname if c in string.printable)
        suname = shortstr(remove_accents(s.username.lower()), delim)
        suname = ''.join(c for c in suname if c in string.printable)

        ogg = f'{s.id}-{suname}-{sname}-{sdur}.ogg'
        wav = f'{s.id}-{suname}-{sname}-{sdur}.wav'

        if downloadAudio:
            outDirFile = os.path.join(outDir, soundtag)
            os.makedirs(outDirFile, exist_ok=True)

            print(f'downloading sound {soundid}, noise type {soundtag}, {sdur} s')
            s.retrieve_preview_hq_ogg(outDirFile, ogg)

            if os.path.isfile(os.path.join(outDirFile, ogg)):
                strSrcFileInfo = f'{s.type}-{ssrate}kHz'
                if s.type != 'wav':
                    strSrcFileInfo += f'-{sbrate}bps'
                print(f'  from {s.previews.preview_hq_ogg}  ({s.type}, {ssrate}ksps{f", {sbrate}kbps" if s.type != "wav" else ""})')

                cmd = f'ffprobe -v error -show_entries stream=sample_rate,bit_rate -of default=noprint_wrappers=1 "{os.path.join(outDirFile, ogg)}"'
                output = subprocess.check_output(cmd, shell=True).decode('utf-8').splitlines()
                sps = bps = ''
                for ln in output:
                    if ln.startswith('sample_rate='):
                        sps = ln.split('=')[1]
                    if ln.startswith('bit_rate='):
                        bps = ln.split('=')[1]
                strTgtFileInfo = f'ogg-{sps}Hz-{bps}bps'
                ssps = f'{float(sps)/1000:.1f}' if sps else '-'
                sbps = f'{float(bps)/1000:.1f}' if bps else '-'
                print(f'  to {os.path.join(outDirFile, ogg)} (ogg, {ssps}ksps, {sbps}kbps)')

                cmd = f'ffmpeg -i "{os.path.join(outDirFile, ogg)}" -ar 16000 -ac 1 -y "{os.path.join(outDirFile, wav)}"'
                subprocess.run(cmd, shell=True, check=True)
                print(f'  converting to {os.path.join(outDirFile, wav)} (wav, 16-bit PCM, 16ksps)')

                if os.path.isfile(os.path.join(outDirFile, wav)):
                    fout.write(f'{soundtag} {s.id} {suname} {sname} {sdur} {strSrcFileInfo} {strTgtFileInfo} {",".join(s.tags)}\n')
                    fout.flush()
                    fnl.write(f'{os.path.join(outDirFile, wav)}\n')
                    fnl.flush()

                os.remove(os.path.join(outDirFile, ogg))

        if not downloadAudio:
            time.sleep(2)