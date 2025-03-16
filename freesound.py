# The MIT License (MIT)
# Copyright (c) 2013-2014 Universitat Pompeu Fabra
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
import re
import json
from urllib.request import urlopen, Request
from urllib.parse import urlencode, quote
from urllib.error import HTTPError


class URIS:
    HOST = 'www.freesound.org'
    BASE = 'https://' + HOST + '/apiv2'
    TEXT_SEARCH = '/search/text/'
    CONTENT_SEARCH = '/search/content/'
    COMBINED_SEARCH = '/sounds/search/combined/'
    SOUND = '/sounds/<sound_id>/'
    USER = '/users/<username>/'
    USER_SOUNDS = '/users/<username>/sounds/'
    USER_PACKS = '/users/<username>/packs/'
    PACK = '/packs/<pack_id>/'
    PACK_SOUNDS = '/packs/<pack_id>/sounds/'
    DOWNLOAD = '/sounds/<sound_id>/download/'
    ANALYSIS = '/sounds/<sound_id>/analysis/'
    SIMILAR_SOUNDS = '/sounds/<sound_id>/similar/'
    COMMENTS = '/sounds/<sound_id>/comments/'
    SOUND_ANALYSIS = '/sounds/<sound_id>/analysis/<filter>/'

    @classmethod
    def uri(cls, uri, *args):
        for a in args:
            uri = re.sub(r'<[\w_]+>', quote(str(a)), uri, 1)
        return cls.BASE + uri


class FreesoundClient:
    client_secret = ""
    client_id = ""
    token = ""
    header = ""

    def get_sound(self, sound_id):
        uri = URIS.uri(URIS.SOUND, sound_id)
        return FSRequest.request(uri, {}, self, Sound)

    def text_search(self, **params):
        uri = URIS.uri(URIS.TEXT_SEARCH)
        return FSRequest.request(uri, params, self, Pager)

    def content_based_search(self, **params):
        uri = URIS.uri(URIS.CONTENT_SEARCH)
        return FSRequest.request(uri, params, self, Pager)

    def combined_search(self, **params):
        uri = URIS.uri(URIS.COMBINED_SEARCH)
        return FSRequest.request(uri, params, self, CombinedSearchPager)

    def get_user(self, username):
        uri = URIS.uri(URIS.USER, username)
        return FSRequest.request(uri, {}, self, User)

    def get_pack(self, pack_id):
        uri = URIS.uri(URIS.PACK, pack_id)
        return FSRequest.request(uri, {}, self, Pack)

    def set_token(self, token, auth_type="token"):
        self.token = token
        self.header = 'Bearer ' + token if auth_type == 'oauth' else 'Token ' + token


class FreesoundObject:
    def __init__(self, json_dict, client):
        self.client = client

        def replace_dashes(d):
            for k, v in list(d.items()):
                if "-" in k:
                    d[k.replace("-", "_")] = d[k]
                    del d[k]
                if isinstance(v, dict):
                    replace_dashes(v)

        replace_dashes(json_dict)
        self.__dict__.update(json_dict)
        for k, v in json_dict.items():
            if isinstance(v, dict):
                self.__dict__[k] = FreesoundObject(v, client)


class FreesoundException(Exception):
    def __init__(self, http_code, detail):
        self.code = http_code
        self.detail = detail

    def __str__(self):
        return f'<FreesoundException: code={self.code}, detail="{self.detail}">'


class FSRequest:
    @classmethod
    def request(cls, uri, params=None, client=None, wrapper=FreesoundObject, method='GET', data=None):
        p = params if params else {}
        url = f'{uri}?{urlencode(p)}' if params else uri
        d = urlencode(data).encode('utf-8') if data else None
        headers = {'Authorization': client.header}
        req = Request(url, data=d, headers=headers)
        try:
            with urlopen(req) as f:
                resp = f.read().decode('utf-8')
        except HTTPError as e:
            resp = e.read().decode('utf-8')
            if 200 <= e.code < 300:
                return resp
            else:
                raise FreesoundException(e.code, json.loads(resp))
        result = json.loads(resp)
        if wrapper:
            return wrapper(result, client)
        return result

    @classmethod
    def retrieve(cls, url, client, path):
        print(f'  from {url}', end='')
        req = Request(url, headers={'Authorization': client.header})
        with urlopen(req) as response, open(path, 'wb') as out_file:
            out_file.write(response.read())
        print()
        return path


class Pager(FreesoundObject):
    def __getitem__(self, key):
        return Sound(self.results[key], self.client)

    def next_page(self):
        return FSRequest.request(self.next, {}, self.client, Pager)

    def previous_page(self):
        return FSRequest.request(self.previous, {}, self.client, Pager)


class CombinedSearchPager(FreesoundObject):
    def __getitem__(self, key):
        return Sound(self.results[key], None)

    def more(self):
        return FSRequest.request(self.more, {}, self.client, CombinedSearchPager)


class Sound(FreesoundObject):
    def retrieve(self, directory, soundid, name=False):
        path = os.path.join(directory, name if name else self.name)
        uri = URIS.uri(URIS.DOWNLOAD, soundid)
        return FSRequest.retrieve(uri, self.client, path)

    def retrieve_preview_hq_ogg(self, directory, name=False):
        path = os.path.join(directory, name if name else self.previews.preview_hq_ogg.split("/")[-1])
        return FSRequest.retrieve(self.previews.preview_hq_ogg, self.client, path)

    def retrieve_preview_hq_mp3(self, directory, name=False):
        path = os.path.join(directory, name if name else self.previews.preview_hq_mp3.split("/")[-1])
        return FSRequest.retrieve(self.previews.preview_hq_mp3, self.client, path)

    def retrieve_preview_lq_ogg(self, directory, name=False):
        path = os.path.join(directory, name if name else self.previews.preview_lq_ogg.split("/")[-1])
        return FSRequest.retrieve(self.previews.preview_lq_ogg, self.client, path)

    def retrieve_preview_lq_mp3(self, directory, name=False):
        path = os.path.join(directory, name if name else self.previews.preview_lq_mp3.split("/")[-1])
        return FSRequest.retrieve(self.previews.preview_lq_mp3, self.client, path)

    def get_analysis(self, descriptors=None):
        uri = URIS.uri(URIS.SOUND_ANALYSIS, self.id)
        params = {'descriptors': descriptors} if descriptors else {}
        return FSRequest.request(uri, params, self.client, FreesoundObject)

    def get_similar(self):
        uri = URIS.uri(URIS.SIMILAR_SOUNDS, self.id)
        return FSRequest.request(uri, {}, self.client, Pager)

    def get_comments(self):
        uri = URIS.uri(URIS.COMMENTS, self.id)
        return FSRequest.request(uri, {}, self.client, Pager)

    def __repr__(self):
        return f'<Sound: id="{self.id}", name="{self.name}">'


class User(FreesoundObject):
    def get_sounds(self):
        uri = URIS.uri(URIS.USER_SOUNDS, self.username)
        return FSRequest.request(uri, {}, self.client, Pager)

    def get_packs(self):
        uri = URIS.uri(URIS.USER_PACKS, self.username)
        return FSRequest.request(uri, {}, self.client, Pager)

    def __repr__(self):
        return f'<User: username="{self.username}">'


class Pack(FreesoundObject):
    def get_sounds(self):
        uri = URIS.uri(URIS.PACK_SOUNDS, self.id)
        return FSRequest.request(uri, {}, self.client, Pager)

    def __repr__(self):
        return f'<Pack: name="{self.get("name", "n.a.")}">'


if __name__ == "__main__":
    # 示例用法
    client = FreesoundClient()
    client.set_token("your_api_token_here", "token")
    sound = client.get_sound(12345)
    print(sound)