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

import random
import sys
import os
import re
import argparse
from functools import partial
import signal


def initRandom(file, seed):
    global rnd, rndidx
    rndidx = 0
    rnd = []
    with open(file, 'r', encoding='utf-8') as f:
        rnd = [l.strip() for l in f.readlines()]

    rndidx = 0 if seed in ('', '0') else int(seed) % len(rnd)
    return rnd


def getRandom(nvalues):
    global rnd, rndidx
    maxint = 9223372036854775807
    out = int(float(nvalues) * float(rnd[rndidx]) / float(maxint))
    rndidx = (rndidx + 1) % len(rnd)
    return out


def listShuffle(l):
    global rnd, rndidx
    idx = list(range(len(l)))
    for i in range(len(l)):
        ri1 = getRandom(len(l))
        idx[i], idx[ri1] = idx[ri1], idx[i]
    return [l[i] for i in idx]


def randomChoice(l):
    return l[getRandom(len(l))]


def sigint_handler(signum, frame):
    print('captured!')
    sys.exit(1)


def buildFileName(fileName, codecs):
    s = os.path.splitext(fileName)
    fileNoExt, ext = s[0], s[1]
    print(' '.join(codecs))
    codecs2 = []
    for c in codecs:
        if 'noise' in c:
            m = re.search(r'snr=([0-9]+)', c)
            c = f'noisy.snr{m.group(1)}' if m else 'noisy'
        codecs2.append(c)

    codecstr = '-'.join(codecs2).replace('|', '').replace('\\', '').replace('[]=', '').replace('[,', '.').replace('/', '')
    return f'{fileNoExt}-{codecstr}{ext}' if codecs else f'{fileNoExt}{ext}'


def fileEmpty(fileName):
    return not os.path.exists(fileName) or os.path.getsize(fileName) <= 2


parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
parser.add_argument("-s", dest="seed", default='0', help="Seed to initialize the random number generator")
parser.add_argument('condition', nargs='?', help="Acoustic condition ([nocodec|landline|cellular|satellite|voip|interview|playback].[clean|noisy08|noisy15]")
parser.add_argument("-D", dest="deviceirlist", default='ir-device-file-list.txt', help="Device impulse response file list")
parser.add_argument("-P", dest="spaceirlist", default='ir-space-file-list.txt', help="Space impulse response file list")
parser.add_argument("-N", dest="noiselist", default='noise-file-list.txt', help="Noise file list")
parser.add_argument('filelist', nargs='?', help="File list to process")
parser.add_argument('outdir', nargs='?')
options = parser.parse_args()

initRandom('random', options.seed)

argcond = 'all' if options.condition == '-' else options.condition
fileList = options.filelist
outDir = options.outdir

cmdFile = f'./degrade-audio-safe-random.py -D {options.deviceirlist} -P {options.spaceirlist} -N {options.noiselist}'
signal.signal(signal.SIGINT, partial(sigint_handler))

try:
    with open(fileList, encoding='utf-8') as f:
        files = [line.strip() for line in f]
except Exception as e:
    print(f'could not read file {fileList}: {e}')
    sys.exit(1)

cond, ncond, ncondsnr = '', '', ''
s = argcond.split('.')
if len(s) > 0:
    cond = s[0]
if len(s) > 1:
    if s[1] in ('clean', ''):
        ncond = ''
    elif s[1] in ('noisy08', 'noisy15', 'noisy25'):
        ncond, ncondsnr = s[1][:-2], s[1][-2:]
    else:
        print('the noisy condition should be either noisy08 or noisy15')
        sys.exit(0)

outDirCond = os.path.join(outDir, cond if ncond == '' else f'{cond}.{ncond}{ncondsnr}')
os.makedirs(outDirCond, exist_ok=True)

print(f'doing condition {cond}{"." + ncond if ncond else ""} (no noise condition)' if ncond == '' else f'doing condition {cond}.{ncond}')

with open(f'{outDirCond}.scp', 'w', encoding='utf-8') as fscp:
    noiseConditions = ['clean', 'ambience-babble', 'ambience-private', 'ambience-music', 'ambience-nature', 'ambience-transportation', 'ambience-outdoors', 'ambience-public', 'ambience-impulsive']
    codecConditions = ['nocodec', 'landline', 'cellular', 'satellite', 'voip', 'interview', 'playback']
    levels = [-26, -29, -32, -35]
    noiseTypes = ['ambience-babble', 'ambience-private', 'ambience-music', 'ambience-transportation', 'ambience-outdoors', 'ambience-public', 'ambience-impulsive']

    codecsLandline = ['g711', 'g726']
    codecsCellular = ['amr', 'amrwb', 'gsmfr']
    codecsSatellite = ['g728', 'c2', 'cvsd']
    codecsVoIP = ['silk', 'silkwb', 'g729a', 'g722']
    codecsInterview = ['mp3', 'aac']
    codecsPlayback = ['mp3', 'aac']
    codecsBPFilter = ['g711', 'g726', 'amr', 'gsmfr', 'g728']

    amrParms = ['amr[mode=0]', 'amr[mode=1]', 'amr[mode=2]', 'amr[mode=3]', 'amr[mode=4]', 'amr[mode=5]', 'amr[mode=6]', 'amr[mode=7]']
    amrwbParms = ['amrwb[mode=0]', 'amrwb[mode=1]', 'amrwb[mode=2]', 'amrwb[mode=3]', 'amrwb[mode=4]', 'amrwb[mode=5]', 'amrwb[mode=6]', 'amrwb[mode=7]', 'amrwb[mode=8]']
    g711Parms = ['g711[law=u]', 'g711[law=a]']
    g726Parms = ['g726[bitrate=16]', 'g726[bitrate=24]', 'g726[bitrate=32]', 'g726[bitrate=40]']
    g729aParms = ['g729a']
    g722Parms = ['g722']
    g728Parms = ['g728']
    c2Parms = ['c2']
    cvsdParms = ['cvsd']
    silkParms = ['silk[bitrate=5]', 'silk[bitrate=10]', 'silk[bitrate=15]', 'silk[bitrate=20]']
    silkwbParms = ['silkwb[bitrate=10]', 'silkwb[bitrate=20]', 'silkwb[bitrate=30]', 'silkwb[bitrate=40]']
    gsmfrParms = ['gsmfr']
    mp3Parms = ['mp3[bitrate=8]', 'mp3[bitrate=16]', 'mp3[bitrate=24]', 'mp3[bitrate=32]', 'mp3[bitrate=40]', 'mp3[bitrate=48]', 'mp3[bitrate=56]', 'mp3[bitrate=64]']
    aacParms = ['aac[bitrate=8]', 'aac[bitrate=16]', 'aac[bitrate=24]', 'aac[bitrate=32]', 'aac[bitrate=40]', 'aac[bitrate=48]', 'aac[bitrate=56]', 'aac[bitrate=64]']
    bpParms = ['bp[cutoff=300-3400]', 'bp[cutoff=200-3600]', 'bp[cutoff=100-3800]']

    for nf, f in enumerate(files):
        level = randomChoice(levels)
        codecList = [f'norm[rms={level}]']

        if ncond:
            opt = f'noise[filter=ambience-public|ambience-private|ambience-outdoors|ambience-babble|ambience-transportation|ambience-music,snr={ncondsnr}]'
            codecList.append(opt)

        codecList2 = []
        if cond == 'landline':
            codec = randomChoice(codecsLandline)
            if codec in codecsBPFilter:
                codecList2.append(randomChoice(bpParms))
            codecList2.append(randomChoice(eval(f'{codec}Parms')))
        elif cond == 'cellular':
            codec = randomChoice(codecsCellular)
            if codec in codecsBPFilter:
                codecList2.append(randomChoice(bpParms))
            codecList2.append(randomChoice(eval(f'{codec}Parms')))
        elif cond == 'satellite':
            codec = randomChoice(codecsSatellite)
            if codec in codecsBPFilter:
                codecList2.append(randomChoice(bpParms))
            codecList2.append(randomChoice(eval(f'{codec}Parms')))
        elif cond == 'voip':
            codec = randomChoice(codecsVoIP)
            codecList2.append(randomChoice(eval(f'{codec}Parms')))
        elif cond == 'playback':
            codec = randomChoice(codecsPlayback)
            codecList2.append(randomChoice(eval(f'{codec}Parms')))
        elif cond == 'interview':
            codec = randomChoice(codecsInterview)
            codecList2.append(randomChoice(eval(f'{codec}Parms')))
        elif cond == 'nocodec':
            pass

        codecs = codecList + codecList2
        outputFile = os.path.join(outDirCond, buildFileName(os.path.basename(f), codecs))
        outputFile = os.path.splitext(outputFile)[0] + '.wav'

        if fileEmpty(outputFile):
            cmd = f'{cmdFile} {"-s " + str(rndidx) if options.seed else ""} -r 8000 -c {":".join(codecs)} "{f}" "{outputFile}"'
            print(cmd)
            os.system(cmd)
            print('\n')
        fscp.write(f'{outputFile}\n')
        fscp.flush()