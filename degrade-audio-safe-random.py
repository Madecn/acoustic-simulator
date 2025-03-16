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

import argparse
import os
import subprocess
import re
import random
import string
from math import ceil


scriptDir = os.path.dirname(os.path.abspath(__file__))
tmpDir = os.path.join(scriptDir, 'tmp', ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(15)))
os.makedirs(tmpDir, exist_ok=True)

ffmpegBin = 'ffmpeg'  # 假设已安装并在 PATH 中
soxBin = 'sox -V1'    # 假设已安装并在 PATH 中

codecStr = (
    '\n'
    '\n\'noise[opts]\': Add noise (opts: filter=keyword, snr=snr(dB), irspace=keyword, wet=(0-100))\n'
    '\'norm[opts]\': Normalize audio (opts: rms=level(dB))\n'
    '\'bp[opts]\': Apply bandpass filter (opts: cutoff=freqLo-freqHi(Hz))\n'
    '\'amr[opts]\': AMR narrowband codec (opts: mode=[0-7])\n'
    '\'amrwb[opts]\': AMR wideband codec (opts: mode=[0-8])\n'
    '\'g711[opts]\': G.711 codec (opts: law=[u|a])\n'
    '\'g726[opts]\': G.726 codec (opts: bitrate=[16|24|32|40])\n'
    '\'g729a\': G.729a codec\n'
    '\'g722\': G.722 codec\n'
    '\'g728\': G.728 codec\n'
    '\'c2\': C2 codec\n'
    '\'cvsd\': CVSD codec\n'
    '\'silk[opts]\': SILK codec (opts: bitrate=[5|10|15|20])\n'
    '\'silkwb[opts]\': SILK wideband codec (opts: bitrate=[10|20|30|40])\n'
    '\'gsmfr\': GSM-FR codec\n'
    '\'mp3[opts]\': MP3 codec (opts: bitrate=[8|16|24|32|40|48|56|64])\n'
    '\'aac[opts]\': AAC codec (opts: bitrate=[8|16|24|32|40|48|56|64])\n'
)

maxint = 9223372036854775807
rnd = []
rndidx = 0


def initRandom(file, seed):
    global rnd, rndidx
    rndidx = 0
    with open(file, 'r', encoding='utf-8') as f:
        rnd.extend(l.strip() for l in f.readlines())
    rndidx = 0 if seed in ('', '0') else int(seed) % len(rnd)
    return rnd


def getRandom(nvalues):
    global rnd, rndidx
    out = int(float(nvalues) * float(rnd[rndidx]) / float(maxint))
    rndidx = (rndidx + 1) % len(rnd)
    return out


def randomChoice(l):
    return l[getRandom(len(l))]


def getCodecs(options):
    if not options.codecs:
        return [], []
    codecs = options.codecs.split(':')
    opts = []
    for c in codecs:
        m = re.search(r'\[(.*)\]', c)
        opts.append(m.group(1) if m else '')
        codecs[codecs.index(c)] = re.sub(r'\[.*\]', '', c)
    return codecs, opts


def getAudioStats(filename, soxopts=''):
    cmd = f'{soxBin} {soxopts} "{filename}" -n stat'
    s = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode('utf-8').splitlines()
    nSamples = lengthSec = rmsAmplitude = None
    for ln in s:
        m = re.search(r'Samples read:\s+([0-9]+)', ln)
        if m:
            nSamples = int(m.group(1))
        m = re.search(r'Length \(seconds\):\s+([0-9]+\.[0-9]+)', ln)
        if m:
            lengthSec = float(m.group(1))
        m = re.search(r'RMS\s+amplitude:\s+([0-9]+\.[0-9]+)', ln)
        if m:
            rmsAmplitude = float(m.group(1))
    return nSamples, lengthSec, rmsAmplitude


def getSpeechRMSAmp(filename, soxopts=''):
    tmp = os.path.join(tmpDir, f'{os.path.basename(filename)}-getSpeechRMSAmp.raw')
    subprocess.run(f'{soxBin} {soxopts} "{filename}" "{tmp}" vad', shell=True, check=True)
    if os.path.getsize(tmp) > 0:
        s = subprocess.check_output(f'{soxBin} {soxopts} "{tmp}" -n stat', shell=True, stderr=subprocess.STDOUT).decode('utf-8').splitlines()
        os.remove(tmp)
    else:
        s = subprocess.check_output(f'{soxBin} {soxopts} "{filename}" -n stat', shell=True, stderr=subprocess.STDOUT).decode('utf-8').splitlines()
    
    for ln in s:
        m = re.search(r'RMS\s+amplitude:\s+([0-9]+\.[0-9]+)', ln)
        if m:
            return float(m.group(1))
    return None


parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
parser.add_argument("-r", dest="samplerate", default='auto', help="Force output sample rate")
parser.add_argument("-s", dest="seed", default='', help="Seed to initialize the random number generator")
parser.add_argument("-c", dest="codecs", default='', help=f"Colon-separated list of codecs to apply in order{codecStr}")
parser.add_argument("-D", dest="deviceirlist", default='ir-device-file-list.txt', help="Device impulse response file list")
parser.add_argument("-P", dest="spaceirlist", default='ir-space-file-list.txt', help="Space impulse response file list")
parser.add_argument("-N", dest="noiselist", default='noise-file-list.txt', help="Noise file list")
parser.add_argument("-d", dest="debug", action="store_true", help="Debug mode")
parser.add_argument('inputFile', help="Input audio file")
parser.add_argument('outputFile', help="Output audio file")
options = parser.parse_args()

initRandom('random', options.seed)

noiseFiles = []
if os.path.exists(options.noiselist):
    with open(options.noiselist, encoding='utf-8') as f:
        noiseFiles = [line.strip() for line in f if line.strip()]

deviceIRs = []
if os.path.exists(options.deviceirlist):
    with open(options.deviceirlist, encoding='utf-8') as f:
        deviceIRs = [line.strip() for line in f if line.strip()]

spaceIRs = []
if os.path.exists(options.spaceirlist):
    with open(options.spaceirlist, encoding='utf-8') as f:
        spaceIRs = [line.strip() for line in f if line.strip()]

inputFile = options.inputFile
outputFile = options.outputFile
fileIn = inputFile
rmTmp = not options.debug

if options.debug:
    print('keeping all temporary files for debug')

stepNo = 0
random.seed(int(options.seed) if options.seed else None)

fext = os.path.splitext(fileIn)[1]
fileInRaw = os.path.join(tmpDir, f'{os.path.basename(fileIn)}.raw')
fileInRawIni = fileInRaw

if fext == '.sph':
    fileInWavTmp = re.sub('.raw', '-tmp.wav', fileInRaw)
    subprocess.run(f'sph2pipe -p -f rif -c 1 "{fileIn}" "{fileInWavTmp}"', shell=True, check=True)
    subprocess.run(f'{soxBin} "{fileInWavTmp}" -G -V0 -r 16000 -c 1 "{fileInRaw}" rate -h', shell=True, check=True)
    os.remove(fileInWavTmp)
else:
    subprocess.run(f'{soxBin} "{fileIn}" -G -V0 -r 16000 -c 1 "{fileInRaw}" rate -h', shell=True, check=True)

fileInRate = 16000
for codec, opts in zip(*getCodecs(options)):
    print(f'\napplying {codec}')
    fileInRawCodec = re.sub('.raw', f'-{stepNo}-tmp0-{codec}.raw', fileInRaw)
    fileOutTmp1Raw = re.sub('.raw', f'-{stepNo}-tmp1-{codec}.raw', fileInRaw)
    fileOutTmp2Raw = re.sub('.raw', f'-{stepNo}-tmp2-{codec}.raw', fileInRaw)
    fileOutTmp3Raw = re.sub('.raw', f'-{stepNo}-tmp3-{codec}.raw', fileInRaw)
    fileOutTmp4Raw = re.sub('.raw', f'-{stepNo}-tmp4-{codec}.raw', fileInRaw)
    fileOutRaw = re.sub('.raw', f'-{stepNo}-{codec}.raw', fileInRaw)

    if codec == 'noise':
        if not noiseFiles:
            print('no noise files available')
            continue
        noiseFile = randomChoice(noiseFiles)
        nSamplesNoise, lengthSecNoise, rmsAmpNoise = getAudioStats(noiseFile)
        nSamplesSpeech, lengthSecSpeech, rmsAmpSpeech = getAudioStats(fileInRaw, f'-t raw -e signed-integer -b 16 -r {fileInRate}')
        speechRMSAmp = getSpeechRMSAmp(fileInRaw, f'-t raw -e signed-integer -b 16 -r {fileInRate}')
        snr = 15
        m = re.search(r'snr=([0-9]+)', opts)
        if m:
            snr = float(m.group(1))
        noiseScaling = speechRMSAmp / rmsAmpNoise / (10**(snr/20))
        posStart = getRandom(int(max(0, lengthSecNoise - lengthSecSpeech) * fileInRate))
        posEnd = posStart + nSamplesSpeech
        subprocess.run(f'{soxBin} "{noiseFile}" -G -t raw -e signed-integer -b 16 -r {fileInRate} "{fileOutTmp2Raw}" trim {posStart / fileInRate} {posEnd / fileInRate}', shell=True, check=True)
        subprocess.run(f'{soxBin} -m -t raw -e signed-integer -b 16 -r {fileInRate} "{fileInRaw}" -t raw -e signed-integer -b 16 -r {fileInRate} -v {noiseScaling} "{fileOutTmp2Raw}" "{fileOutTmp4Raw}"', shell=True, check=True)
    elif codec == 'norm':
        m = re.search(r'rms=([-+]?[0-9]+)', opts)
        if m:
            level = float(m.group(1))
            gain = 10**(level/20) / getSpeechRMSAmp(fileInRaw, f'-t raw -e signed-integer -b 16 -r {fileInRate}')
            subprocess.run(f'{soxBin} -t raw -e signed-integer -b 16 -r {fileInRate} "{fileInRaw}" -G "{fileOutTmp4Raw}" gain {gain}', shell=True, check=True)
    elif codec == 'bp':
        m = re.search(r'cutoff=([0-9]+)-([0-9]+)', opts)
        if m:
            freqLo, freqHi = m.group(1), m.group(2)
            subprocess.run(f'{soxBin} -t raw -e signed-integer -b 16 -r {fileInRate} "{fileInRaw}" "{fileOutTmp4Raw}" sinc {freqLo}-{freqHi}', shell=True, check=True)
    else:
        # 示例编解码器处理（需要根据实际工具调整）
        subprocess.run(f'{soxBin} -t raw -e signed-integer -b 16 -r {fileInRate} "{fileInRaw}" "{fileOutTmp4Raw}"', shell=True, check=True)

    subprocess.run(f'cp "{fileOutTmp4Raw}" "{fileOutRaw}"', shell=True, check=True)
    if rmTmp:
        for tmp in [fileInRawCodec, fileOutTmp1Raw, fileOutTmp2Raw, fileOutTmp3Raw, fileOutTmp4Raw]:
            if os.path.exists(tmp):
                os.remove(tmp)
    fileInRaw = fileOutRaw
    stepNo += 1

if options.samplerate == 'auto':
    options.samplerate = fileInRate

fileName, fileExtension = os.path.splitext(outputFile)
outext = fileExtension[1:]
subprocess.run(f'{soxBin} -t raw -e signed-integer -b 16 -r {fileInRate} "{fileInRaw}" -t {outext} -r {options.samplerate} "{outputFile}"', shell=True, check=True)

if rmTmp:
    os.remove(fileInRawIni)
    os.rmdir(tmpDir)