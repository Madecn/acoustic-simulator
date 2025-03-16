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

import os
import subprocess
import numpy as np
import soundfile as sf  # 替换 scikits.audiolab
import librosa  # 替换 scikits.samplerate


def loadSignal(fileName):
    try:
        x, Fs = sf.read(fileName)
    except Exception as e:
        print(f'Could not import file "{fileName}": {e}')
        return None, None
    return x, Fs


irOriginal = 'impulse-responses-original'
irOutput = 'impulse-responses'
irDeviceList = 'ir-device-file-list.txt'
irSpaceList = 'ir-space-file-list.txt'

kwDevice = ['devices']
kwSpace = ['spaces']
kwBlockSpace = []

# 获取 WAV 文件列表（Windows 兼容）
swav = subprocess.check_output(f'dir /s /b "{irOriginal}\\*.wav"', shell=True).decode('utf-8')
swav = swav.splitlines()

nDevice = 0
nSpace = 0

with open(irDeviceList, 'w', encoding='utf-8') as fdevice, \
     open(irSpaceList, 'w', encoding='utf-8') as fspace:
    for ln in swav:
        ln = ln.strip()
        if not ln:
            continue

        fileName, fileExtension = os.path.splitext(ln)
        x, fs = loadSignal(ln)
        if x is None:
            continue

        sx = x.shape
        if len(sx) == 2:
            ir = x[:, 1]  # 取右声道
        elif len(sx) == 1:
            ir = x
        else:
            print(f'too many channels for IR {ln}: skipping')
            continue

        # 重采样到 8kHz 和 16kHz 并归一化
        ir8k = librosa.resample(ir, orig_sr=fs, target_sr=8000)
        ir8kabs = ir8k * ir8k
        sum8k = ir8kabs.sum()
        ir8k = ir8k / np.sqrt(sum8k) if sum8k > 0 else ir8k

        dname = os.path.dirname(ln)
        lin = dname.split(os.sep)[1:]
        lout = [''.join(c for c in elem if c.isalnum()) for elem in lin]
        outdir = os.path.join(irOutput, *lout)

        basename = os.path.basename(ln)
        basename = re.sub(r'.wav', '', basename)
        basename = ''.join(c for c in basename if c.isalnum())

        basename8k = f'{basename}-8000.ir'
        outfile8k = os.path.join(outdir, basename8k)

        ir16k = librosa.resample(ir, orig_sr=fs, target_sr=16000)
        ir16kabs = ir16k * ir16k
        sum16k = ir16kabs.sum()
        ir16k = ir16k / np.sqrt(sum16k) if sum16k > 0 else ir16k
        basename16k = f'{basename}-16000.ir'
        outfile16k = os.path.join(outdir, basename16k)

        foundSpace = any(kw in dname for kw in kwSpace) and not any(kw in dname for kw in kwBlockSpace)
        foundDevice = any(kw in dname for kw in kwDevice)

        if foundDevice:
            os.makedirs(outdir, exist_ok=True)
            print(ln)
            np.savetxt(outfile8k, ir8k, fmt='%f', delimiter=' ')
            np.savetxt(outfile16k, ir16k, fmt='%f', delimiter=' ')
            fdevice.write(f'{outfile16k}\n')
            nDevice += 1

        if foundSpace:
            os.makedirs(outdir, exist_ok=True)
            print(ln)
            np.savetxt(outfile8k, ir8k, fmt='%f', delimiter=' ')
            np.savetxt(outfile16k, ir16k, fmt='%f', delimiter=' ')
            fspace.write(f'{outfile16k}\n')
            nSpace += 1

print(f'{nDevice} device IRs')
print(f'{nSpace} space IRs')