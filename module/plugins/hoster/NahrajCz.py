# -*- coding: utf-8 -*-

from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from ..internal.DeadHoster import DeadHoster


class NahrajCz(DeadHoster):
    __name__ = "NahrajCz"
    __type__ = "hoster"
    __version__ = "0.26"
    __status__ = "stable"

    __pattern__ = r'http://(?:www\.)?nahraj\.cz/content/download/.+'
    __config__ = []  # @TODO: Remove in 0.4.10

    __description__ = """Nahraj.cz hoster plugin"""
    __license__ = "GPLv3"
    __authors__ = [("zoidberg", "zoidberg@mujmail.cz")]
