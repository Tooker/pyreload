#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    This program is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 3 of the License,
    or (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
    See the GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program; if not, see <http://www.gnu.org/licenses/>.

    @author: RaNaN
"""

from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from logging import getLogger
from os import remove
from os.path import dirname
from shutil import move
from time import time

import pycurl

from module.plugins.Plugin import Abort
from module.utils import (
    fs_encode,
    save_join,
)

from .HTTPChunk import (
    ChunkInfo,
    HTTPChunk,
)
from .HTTPRequest import BadHeader


class HTTPDownload():
    """ loads a url http + ftp """

    def __init__(self, url, filename, get={}, post={}, referer=None, cj=None, bucket=None,
                 options={}, progressNotify=None, disposition=False):
        self.url = url
        # Complete file destination, not only name
        self.filename = filename
        self.get = get
        self.post = post
        self.referer = referer
        # Cookiejar if cookies are needed
        self.cj = cj
        self.bucket = bucket
        self.options = options
        self.disposition = disposition
        # all arguments

        self.abort = False
        self.size = 0
        # Will be parsed from content disposition
        self.nameDisposition = None

        self.chunks = []

        self.log = getLogger("log")

        try:
            self.info = ChunkInfo.load(filename)
            # Resume is only possible with valid info file
            self.info.resume = True
            self.size = self.info.size
            self.infoSaved = True
        except IOError:
            self.info = ChunkInfo(filename)

        self.chunkSupport = None
        self.m = pycurl.CurlMulti()

        # Needed for speed calculation
        self.lastArrived = []
        self.speeds = []
        self.lastSpeeds = [0, 0]

        self.progressNotify = progressNotify

    @property
    def speed(self):
        last = [sum(x) for x in self.lastSpeeds if x]
        return (sum(self.speeds) + sum(last)) / (1 + len(last))

    @property
    def arrived(self):
        return sum([c.arrived for c in self.chunks])

    @property
    def percent(self):
        if not self.size:
            return 0
        return (self.arrived * 100) / self.size

    def _copyChunks(self):
        # Initial chunk name
        init = fs_encode(self.info.getChunkName(0))

        if self.info.getCount() > 1:
            # First chunkfile
            fo = open(init, "rb+")
            for i in range(1, self.info.getCount()):
                # Input file
                # Seek to beginning of chunk, to get rid of overlapping chunks
                fo.seek(self.info.getChunkRange(i - 1)[1] + 1)
                fname = fs_encode("%s.chunk%d" % (self.filename, i))
                fi = open(fname, "rb")
                buf = 32 * 1024

                # Copy in chunks, consumes less memory
                while True:
                    data = fi.read(buf)
                    if not data:
                        break
                    fo.write(data)
                fi.close()
                if fo.tell() < self.info.getChunkRange(i)[1]:
                    fo.close()
                    remove(init)
                    # There are probably invalid chunks
                    self.info.remove()
                    raise Exception("Downloaded content was smaller than expected. Try to reduce download connections.")
                # Remove chunk
                remove(fname)
            fo.close()

        if self.nameDisposition and self.disposition:
            self.filename = save_join(dirname(self.filename), self.nameDisposition)

        move(init, fs_encode(self.filename))
        # Remove info file
        self.info.remove()

    def download(self, chunks=1, resume=False):
        """Returns new filename or None."""

        chunks = max(1, chunks)
        resume = self.info.resume and resume

        try:
            self._download(chunks, resume)
        except pycurl.error as e:
            # Code 33 - no resume
            code = e.args[0]
            if code == 33:
                # Try again without resume
                self.log.debug("Errno 33 -> Restart without resume")

                # Remove old handles
                for chunk in self.chunks:
                    self.closeChunk(chunk)

                return self._download(chunks, False)
            else:
                raise
        finally:
            self.close()

        if self.nameDisposition and self.disposition:
            return self.nameDisposition
        return None

    def _download(self, chunks, resume):
        if not resume:
            self.info.clear()
            # Create an initial entry
            self.info.addChunk("%s.chunk0" % self.filename, (0, 0))

        self.chunks = []

        # Initial chunk that will load complete file (if needed)
        init = HTTPChunk(0, self, None, resume)

        self.chunks.append(init)
        self.m.add_handle(init.getHandle())

        lastFinishCheck = 0
        lastTimeCheck = 0
        # List of curl handles that are finished
        chunksDone = set()
        chunksCreated = False
        done = False

        # This is a resume, if we were chunked originally assume still can
        if self.info.getCount() > 1:
            self.chunkSupport = True

        while 1:
            # Need to create chunks
            # Will be set later by first chunk
            if not chunksCreated and self.chunkSupport and self.size:
                if not resume:
                    self.info.setSize(self.size)
                    self.info.createChunks(chunks)
                    self.info.save()

                chunks = self.info.getCount()

                init.setRange(self.info.getChunkRange(0))

                for i in range(1, chunks):
                    c = HTTPChunk(i, self, self.info.getChunkRange(i), resume)

                    handle = c.getHandle()
                    if handle:
                        self.chunks.append(c)
                        self.m.add_handle(handle)
                    else:
                        # Close immediatly
                        self.log.debug("Invalid curl handle -> closed")
                        c.close()

                chunksCreated = True

            while 1:
                ret, num_handles = self.m.perform()
                if ret != pycurl.E_CALL_MULTI_PERFORM:
                    break

            t = time()

            # Reduce these calls
            while lastFinishCheck + 0.5 < t:
                # List of failed curl handles
                failed = []
                # Save only last exception, we can only raise one anyway
                ex = None

                num_q, ok_list, err_list = self.m.info_read()
                for c in ok_list:
                    chunk = self.findChunk(c)
                    # Check if the header implies success, else add it to failed list
                    try:
                        chunk.verifyHeader()
                    except BadHeader as e:
                        self.log.debug("Chunk %d failed: %s" % (chunk.id + 1, str(e)))
                        failed.append(chunk)
                        ex = e
                    else:
                        chunksDone.add(c)

                for c in err_list:
                    curl, errno, msg = c
                    chunk = self.findChunk(curl)
                    # Test if chunk was finished
                    if errno != 23 or "0 !=" not in msg:
                        failed.append(chunk)
                        ex = pycurl.error(errno, msg)
                        self.log.debug("Chunk %d failed: %s" % (chunk.id + 1, str(ex)))
                        continue
                    # Check if the header implies success, else add it to failed list
                    try:
                        chunk.verifyHeader()
                    except BadHeader as e:
                        self.log.debug("Chunk %d failed: %s" % (chunk.id + 1, str(e)))
                        failed.append(chunk)
                        ex = e
                    else:
                        chunksDone.add(curl)
                        # No more infos to get
                if not num_q:

                    # Check if init is not finished so we reset download connections,
                    # note that other chunks are closed and downloaded with init too
                    if failed and init not in failed and init.c not in chunksDone:
                        self.log.error(_("Download chunks failed, fallback to single connection | %s" % (str(ex))))

                        # List of chunks to clean and remove
                        for chunk in filter(lambda x: x is not init, self.chunks):
                            self.closeChunk(chunk)
                            self.chunks.remove(chunk)
                            remove(fs_encode(self.info.getChunkName(chunk.id)))

                        # Let first chunk load the rest and update the info file
                        init.resetRange()
                        self.info.clear()
                        self.info.addChunk("%s.chunk0" % self.filename, (0, self.size))
                        self.info.save()
                    elif failed:
                        raise ex

                    lastFinishCheck = t

                    if len(chunksDone) >= len(self.chunks):
                        if len(chunksDone) > len(self.chunks):
                            self.log.warning("Finished download chunks size incorrect, please report bug.")
                        # All chunks loaded
                        done = True

                    break
            # All chunks loaded
            if done:
                break

            # Calc speed once per second, averaging over 3 seconds
            if lastTimeCheck + 1 < t:
                diff = [c.arrived - (self.lastArrived[i] if len(self.lastArrived) > i else 0) for i, c in
                        enumerate(self.chunks)]

                self.lastSpeeds[1] = self.lastSpeeds[0]
                self.lastSpeeds[0] = self.speeds
                self.speeds = [float(a) / (t - lastTimeCheck) for a in diff]
                self.lastArrived = [c.arrived for c in self.chunks]
                lastTimeCheck = t
                self.updateProgress()

            if self.abort:
                raise Abort()

            # Sleep(0.003) #supress busy waiting - limits dl speed to  (1 / x) * buffersize
            self.m.select(1)

        for chunk in self.chunks:
            # Make sure downloads are written to disk
            chunk.flushFile()

        self._copyChunks()

    def updateProgress(self):
        if self.progressNotify:
            self.progressNotify(self.percent)

    def findChunk(self, handle):
        """ linear search to find a chunk (should be ok since chunk size is usually low) """
        for chunk in self.chunks:
            if chunk.c == handle:
                return chunk

    def closeChunk(self, chunk):
        try:
            self.m.remove_handle(chunk.c)
        except pycurl.error as e:
            self.log.debug("Error removing chunk: %s" % str(e))
        finally:
            chunk.close()

    def close(self):
        """ cleanup """
        for chunk in self.chunks:
            self.closeChunk(chunk)

        self.chunks = []
        if hasattr(self, "m"):
            self.m.close()
            del self.m
        if hasattr(self, "cj"):
            del self.cj
        if hasattr(self, "info"):
            del self.info


if __name__ == "__main__":
    url = "http://speedtest.netcologne.de/test_100mb.bin"

    from .Bucket import Bucket

    bucket = Bucket()
    bucket.setRate(200 * 1024)
    bucket = None

    print("starting")

    dwnld = HTTPDownload(url, "test_100mb.bin", bucket=bucket)
    dwnld.download(chunks=3, resume=True)
