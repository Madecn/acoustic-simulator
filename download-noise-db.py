#!/usr/bin/python

import freesound
import string
import unicodedata
import time
import glob
import os
import sys
import subprocess
import threading
import queue
from pathlib import Path

apiKey = "bPQdQ891V6d8bHCvaQET7VjjnNEnYshXYrEDGD3A"  # 请填入你的 Freesound API 密钥

downloadAudio = True
delim = ",.?-_:;'\" ()[]{}&^%$#@!~`<>/|"
MAX_THREADS = 20  # 最大线程数

def shortstr(s, ds, l=0):
    for d in ds:
        s = s.replace(d, '').lower()
    return s if l == 0 else s[:l-1]

def remove_accents(input_str):
    nkfd_form = unicodedata.normalize('NFKD', input_str)
    return "".join(c for c in nkfd_form if not unicodedata.combining(c))

def download_sound(sound_info, client, out_dir, fnl, fntl, fout, fr, noisetypes):
    soundid, soundtag, soundlic = sound_info
    g = glob.glob(os.path.join(out_dir, soundtag, f'{soundid}*.wav'))
    if g:
        print(f'skipping file {g[0]}')
        return

    if soundtag not in noisetypes:
        with threading.Lock():
            noisetypes.append(soundtag)
            fntl.write(f'{soundtag}\n')
            fntl.flush()

    try:
        s = client.get_sound(soundid)
        if not isinstance(s, freesound.Sound):
            print(f"Error: Sound ID {soundid} returned unexpected type {type(s)}, skipping")
            return
    except freesound.FreesoundException as e:
        if e.code == 400:
            print(f"Error: Invalid sound ID {soundid} (HTTP 400), skipping")
        elif e.code == 429:
            print('Maximum limit of requests to Freesound reached (2000/day)')
            sys.exit(1)
        else:
            print(f"Error: FreesoundException for sound ID {soundid}: {e}, skipping")
        return
    except Exception as e:
        print(f"Unexpected error for sound ID {soundid}: {e}, skipping")
        return

    if hasattr(s, 'description') and s.description:
        idxcr = s.description.find('\n')
        if idxcr >= 0:
            s.description = s.description[:idxcr]
    else:
        s.description = ""

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
    out_dir_file = os.path.join(out_dir, soundtag)
    os.makedirs(out_dir_file, exist_ok=True)

    ogg_path = os.path.join(out_dir_file, ogg)
    wav_path = os.path.join(out_dir_file, wav)

    if downloadAudio:
        print(f'downloading sound {soundid}, noise type {soundtag}, {sdur} s')
        # 检查是否需要断点续传
        if os.path.exists(ogg_path) and os.path.getsize(ogg_path) > 0:
            print(f"  resuming download for {ogg_path}")
        s.retrieve_preview_hq_ogg(out_dir_file, ogg)

        if os.path.isfile(ogg_path):
            str_src_file_info = f'{s.type}-{ssrate}kHz'
            if s.type != 'wav':
                str_src_file_info += f'-{sbrate}bps'
            print(f'  from {s.previews.preview_hq_ogg}  ({s.type}, {ssrate}ksps{f", {sbrate}kbps" if s.type != "wav" else ""})')

            cmd = f'ffprobe -v error -show_entries stream=sample_rate,bit_rate -of default=noprint_wrappers=1 "{ogg_path}"'
            output = subprocess.check_output(cmd, shell=True).decode('utf-8').splitlines()
            sps = bps = ''
            for ln in output:
                if ln.startswith('sample_rate='):
                    sps = ln.split('=')[1]
                if ln.startswith('bit_rate='):
                    bps = ln.split('=')[1]
            str_tgt_file_info = f'ogg-{sps}Hz-{bps}bps'
            ssps = f'{float(sps)/1000:.1f}' if sps else '-'
            sbps = f'{float(bps)/1000:.1f}' if bps else '-'
            print(f'  to {ogg_path} (ogg, {ssps}ksps, {sbps}kbps)')

            if not os.path.exists(wav_path) or os.path.getsize(wav_path) == 0:
                cmd = f'ffmpeg -i "{ogg_path}" -ar 16000 -ac 1 -y "{wav_path}"'
                subprocess.run(cmd, shell=True, check=True)
                print(f'  converting to {wav_path} (wav, 16-bit PCM, 16ksps)')
            else:
                print(f'  {wav_path} already exists, skipping conversion')

            if os.path.isfile(wav_path):
                with threading.Lock():
                    fout.write(f'{soundtag} {s.id} {suname} {sname} {sdur} {str_src_file_info} {str_tgt_file_info} {",".join(s.tags)}\n')
                    fout.flush()
                    fnl.write(f'{wav_path}\n')
                    fnl.flush()

            os.remove(ogg_path)

def worker(q, client, out_dir, fnl, fntl, fout, fr, noisetypes):
    while True:
        try:
            sound_info = q.get_nowait()
        except queue.Empty:
            break
        download_sound(sound_info, client, out_dir, fnl, fntl, fout, fr, noisetypes)
        q.task_done()

if len(sys.argv) != 2:
    print("Syntax: download-noise-db.py noise-db.txt")
    sys.exit(0)

sound_list = sys.argv[1]
out_dir = 'noise-samples'
os.makedirs(out_dir, exist_ok=True)

c = freesound.FreesoundClient()
c.set_token(apiKey, "oauth2")

files_to_open = [
    open(sound_list, 'r', encoding='utf-8'),
    open('noise-file-list.txt', 'a', encoding='utf-8'),
    open('noise-type-list.txt', 'a', encoding='utf-8'),
]
if downloadAudio:
    files_to_open.append(open(os.path.join(out_dir, 'noise-db.txt'), 'a', encoding='utf-8'))
    files_to_open.append(open(os.path.join(out_dir, 'noise-db-fields.txt'), 'a', encoding='utf-8'))
else:
    files_to_open.append(None)
    files_to_open.append(None)

with files_to_open[0] as f, \
     files_to_open[1] as fnl, \
     files_to_open[2] as fntl, \
     (files_to_open[3] if downloadAudio else open(os.devnull, 'w')) as fout, \
     (files_to_open[4] if downloadAudio else open(os.devnull, 'w')) as fr:
    
    if downloadAudio and os.path.getsize(os.path.join(out_dir, 'noise-db-fields.txt')) == 0:
        fr.write('noise-type sound-id username name duration src-audio-quality tgt-audio-quality tags\n')

    noisetypes = []
    sound_queue = queue.Queue()
    for line in f:
        line = line.strip()
        sound_queue.put(line.split(' '))

    threads = []
    for _ in range(min(MAX_THREADS, sound_queue.qsize())):
        t = threading.Thread(target=worker, args=(sound_queue, c, out_dir, fnl, fntl, fout, fr, noisetypes))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    sound_queue.join()