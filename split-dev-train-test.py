#!/usr/bin/python

# Copyright (c) 2015 Idiap Research Institute, http://www.idiap.ch/
# Written by Marc Ferras <marc.ferras@idiap.ch>,
#
# This file is part of AcSim.
#
# AcSim is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation.
#
# AcSim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with AcSim. If not, see <http://www.gnu.org/licenses/>.

import sys
import random
import os


def initRandom(file, seed):
    global rnd
    global rndidx

    rndidx = 0
    rnd = []
    with open(file, 'r', encoding='utf-8') as f:
        for l in f.readlines():
            rnd.append(l.strip())

    if seed == '' or seed == '0':
        rndidx = 0
    else:
        rndidx = int(seed)
    if rndidx >= len(rnd):
        rndidx = rndidx % len(rnd)

    return rnd


def getRandom():
    global rndidx
    global rnd

    maxint = 9223372036854775807

    out = float(rnd[rndidx]) / float(maxint)

    rndidx = rndidx + 1
    if rndidx == len(rnd):
        rndidx = 0

    return out


def getRandomInt(nvalues):
    global rndidx
    global rnd

    maxint = 9223372036854775807

    out = int(float(nvalues - 1) * float(rnd[rndidx]) / float(maxint))

    rndidx = rndidx + 1
    if rndidx == len(rnd):
        rndidx = 0

    return out


def listShuffle(l):
    global rnd
    global rndidx

    idx = list(range(0, len(l)))
    idxp = list(idx)
    for i in idx:
        ri1 = getRandomInt(len(l))
        itmp = idxp[i]
        idxp[i] = idxp[ri1]
        idxp[ri1] = itmp

    l2 = [l[i] for i in idxp]
    return l2


if len(sys.argv) != 4:
    print('./split-train-test.py noise-file-list.txt train.list test.list')
    sys.exit(0)

fileList = sys.argv[1]
trainList = sys.argv[2]
testList = sys.argv[3]

with open(trainList, 'r', encoding='utf-8') as f:
    train = [line.strip() for line in f.readlines()]

with open(testList, 'r', encoding='utf-8') as f:
    test = [line.strip() for line in f.readlines()]

# generate train and test file names
fileName, fileExtension = os.path.splitext(fileList)
# open output file list for writing
fileListDev = fileName + '-dev' + fileExtension
fileListTrn = fileName + '-trn' + fileExtension
fileListTst = fileName + '-tst' + fileExtension

initRandom('random', 0)

noises = []
with open(fileList, 'r', encoding='utf-8') as f:
    for ln in f.readlines():
        ln = ln.strip()
        noises.append(ln)
noises = listShuffle(noises)

# assign train first
assignedNoises = []
for f in train:
    noise = noises[0]
    if noise not in assignedNoises:
        assignedNoises.append(noise)
        del noises[0]
trainNoises = list(assignedNoises)
print(f'{len(trainNoises)} noise files to train set')
with open(fileListTrn, 'w', encoding='utf-8') as f:
    for line in trainNoises:
        f.write(line + '\n')

# assign test
assignedNoises = []
for f in test:
    noise = noises[0]
    if noise not in assignedNoises:
        assignedNoises.append(noise)
        del noises[0]
testNoises = list(assignedNoises)
print(f'{len(testNoises)} noise files to test set')
with open(fileListTst, 'w', encoding='utf-8') as f:
    for line in testNoises:
        f.write(line + '\n')

# assign dev
devNoises = list(noises)
print(f'{len(devNoises)} noise files to dev set')
with open(fileListDev, 'w', encoding='utf-8') as f:
    for line in devNoises:
        f.write(line + '\n')