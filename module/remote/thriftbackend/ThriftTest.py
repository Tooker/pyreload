#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import sys
import xmlrpclib
from getpass import getpass
from os.path import (
    abspath,
    dirname,
    join,
)
from time import time

from six.moves import input
from thrift import Thrift
from thrift.transport import TTransport

from .Protocol import Protocol
from .Socket import Socket
from .thriftgen.pyload import Pyload
from .thriftgen.pyload.ttypes import *

path = join((abspath(dirname(__file__))), "..","..", "lib")
sys.path.append(path)






def bench(f, *args, **kwargs):
    s = time()
    ret = [f(*args, **kwargs) for i in range(0,100)]
    e = time()
    try:
        print("%s: %f s" % (f._Method__name, e-s))
    except :
        print("%s: %f s" % (f.__name__, e-s))
    return ret

user = input("user ")
passwd = getpass("password ")

server_url = "http%s://%s:%s@%s:%s/" % (
  "",
  user,
  passwd,
  "127.0.0.1",
  7227
)
proxy = xmlrpclib.ServerProxy(server_url, allow_none=True)

bench(proxy.get_server_version)
bench(proxy.status_server)
bench(proxy.status_downloads)
#bench(proxy.get_queue)
#bench(proxy.get_collector)
print()
try:

    # Make socket
    transport = Socket('localhost', 7228, False)

    # Buffering is critical. Raw sockets are very slow
    transport = TTransport.TBufferedTransport(transport)

    # Wrap in a protocol
    protocol = Protocol(transport)

    # Create a client to use the protocol encoder
    client = Pyload.Client(protocol)

    # Connect!
    transport.open()

    print("Login", client.login(user, passwd))

    bench(client.getServerVersion)
    bench(client.statusServer)
    bench(client.statusDownloads)
    #bench(client.getQueue)
    #bench(client.getCollector)

    print()
    print(client.getServerVersion())
    print(client.statusServer())
    print(client.statusDownloads())
    q = client.getQueue()

    for p in q:
      data = client.getPackageData(p.pid)
      print(data)
      print("Package Name: ", data.name)

    # Close!
    transport.close()

except Thrift.TException as tx:
    print('ThriftExpection: %s' % tx.message)
