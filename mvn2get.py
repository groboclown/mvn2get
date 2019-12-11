#!/usr/bin/python3

"""
Tool to download artifact files from Maven 2 style repositories.

Run with the `-h` argument for help.
"""

# Requires Python 3.7

# MIT License
#
# Copyright (c) 2019 Groboclown
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from typing import List, Tuple, Dict, Iterable, Mapping, Optional, Callable, Any
import os
import sys
import re
import hashlib
import argparse
import shutil
import time
import threading
import http.client
import json
import xml.dom.minidom
from xml.parsers.expat import (ExpatError)
import ssl
import urllib.request
import urllib.response
from urllib.error import (HTTPError, URLError)


VERSION = '1.1'


# ---------------------------------------------------------------------------
# User Configuration
class Config:
    """
    User configuration.  Can be set through CLI and/or configuration file.
    """
    problem_file: Optional[str]
    remote_repo_urls: List[str]
    local_repo_urls: List[str]
    pgp_key_servers: List[str]
    acceptable_license_urls: List[str]
    acceptable_license_names: List[str]
    mislabeled_artifact_groups: Dict[str, Tuple[str, str]]

    def __init__(self) -> None:
        self._loaded = False

        # These can also be set by the CLI arguments
        self.outdir = os.path.curdir
        self.show_progress = False
        self.log_level = LOG_WARN
        self.problem_file = None
        self.recursive = False
        self.overwrite = False
        self.do_remote_download = True
        self.include_dep_management = False
        self.check_in_local = True
        self.no_pgp = False
        self.clean_violations = False

        self.progress_indicators = "|/-\\"
        self.remote_repo_urls = list(DEFAULT_REMOTE_REPO_URLS)
        self.local_repo_urls = []
        self.pgp_key_servers = list(DEFAULT_PGP_KEY_SERVERS)
        self.acceptable_license_urls = list(DEFAULT_ACCEPTABLE_LICENSE_URLS)
        self.acceptable_license_names = list(DEFAULT_ACCEPTABLE_LICENSE_NAMES)
        self.allow_unacceptable_licenses = True
        self.allow_no_license = True
        self.mislabeled_artifact_groups = DEFAULT_MISLABELED_ARTIFACT_GROUP

    def can_log(self, level: str) -> int:
        return LOG_MAP[self.log_level] >= LOG_MAP[level]

    def load(self, filename: str) -> None:
        if not os.path.isfile(filename) or self._loaded:
            return

        with open(filename, 'r') as f:
            data = json.load(f)
        self._loaded = True

        self._set_str(data, 'outdir')
        self._set_bool(data, 'show_progress')
        self._set_str_of(data, 'log_level', LOG_MAP.keys())
        self._set_str(data, 'problem_file')
        self._set_bool(data, 'recursive')
        self._set_bool(data, 'overwrite')
        self._set_bool(data, 'do_remote_download')
        self._set_bool(data, 'include_dep_management')
        self._set_bool(data, 'check_in_local')
        self._set_bool(data, 'no_pgp')
        self._set_str(data, 'progress_indicators')
        self._set_list_of_str(data, 'remote_repo_urls')
        self._set_list_of_str(data, 'local_repo_urls')
        self._set_list_of_str(data, 'pgp_key_servers')
        self._set_list_of_str(data, 'acceptable_license_urls')
        self._set_list_of_str(data, 'acceptable_license_names')
        self._set_bool(data, "allow_unacceptable_licenses")
        self._set_bool(data, "allow_no_license")

        # One-off, complex type.
        mag_val = data.get("mislabeled_artifact_groups", None)
        if isinstance(mag_val, Mapping):
            replace = True
            replaced_mag: Dict[str, Tuple[str, str]] = {}
            for key, val in mag_val.items():
                if (
                        isinstance(key, str)
                        and not isinstance(val, str)
                        and isinstance(val, Iterable)
                ):
                    val_list = list(val)
                    if (
                            len(val_list) == 2
                            and isinstance(val_list[0], str)
                            and isinstance(val_list[1], str)
                    ):
                        replaced_mag[key] = (val_list[0], val_list[1])
                        continue
                replace = False
                break
            if replace:
                self.mislabeled_artifact_groups = replaced_mag

    def _set_str(self, data: Dict[str, Any], key: str) -> None:
        val = data.get(key, None)
        if isinstance(val, str):
            setattr(self, key, val)

    def _set_str_of(self, data: Dict[str, Any], key: str, values: Iterable[str]) -> None:
        val = data.get(key, None)
        if val in values:
            setattr(self, key, val)

    def _set_list_of_str(self, data: Dict[str, Any], key: str) -> None:
        val = data.get(key, None)
        if isinstance(val, Iterable):
            conv: List[str] = []
            for check in val:
                if isinstance(check, str):
                    conv.append(check)
                else:
                    return
            setattr(self, key, conv)

    def _set_bool(self, data: Dict[str, Any], key: str) -> None:
        val = data.get(key, None)
        if val in (True, False):
            setattr(self, key, val)


# ---------------------------------------------------------------------------
# GPG Compatibility
GPG_INST: Optional[Any] = None
try:
    import gnupg

    def setup_gpg(outdir: str) -> None:
        global GPG_INST
        try:
            # Different versions of gnupg have different constructors.
            try:
                GPG_INST = gnupg.GPG(homedir=os.path.join(outdir, '.gnupg'))
            except TypeError:
                GPG_INST = gnupg.GPG(gnupghome=os.path.join(outdir, '.gnupg'))
        except RuntimeError:
            # This is thrown if GnuPG binary cannot be found.
            GPG_INST = None
except ModuleNotFoundError:
    # noinspection PyUnusedLocal
    def setup_gpg(outdir: str) -> None:
        pass


# ---------------------------------------------------------------------------
# Basic Logging Declarations

LOG_WARN = 'warn'
LOG_INFO = 'info'
LOG_DEBUG = 'debug'
LOG_TRACE = 'trace'
LOG_MAP = {
    LOG_WARN: 0,
    LOG_INFO: 1,
    LOG_DEBUG: 2,
    LOG_TRACE: 3,
}

PROGRESS_INDEX = [0]


class Problem:
    __slots__ = ('msg', 'artifact_id', 'files', 'file_violation',)

    def __init__(self, artifact_id: str, files: Iterable[str], file_violation: bool, msg: str) -> None:
        self.msg = msg
        self.artifact_id = artifact_id
        self.files = list(files)
        self.file_violation = file_violation

    def __str__(self) -> str:
        if self.file_violation:
            return 'VIOLATION {0} - {1}'.format(self.artifact_id, self.msg)
        return '{0} - {1}'.format(self.artifact_id, self.msg)

    def json(self) -> Dict[str, Any]:
        return {
            "msg": self.msg,
            "artifact": self.artifact_id,
            "files": list(self.files),
            "file_violation": self.file_violation
        }

    def clean_violations(self) -> None:
        if self.file_violation and CONFIG.clean_violations:
            for f in self.files:
                if os.path.isfile(f):
                    info("{0} - file in violation of policies; removing {1}".format(self.artifact_id, f))
                    delete_file(f)


PROBLEMS: List[Problem] = []


def add_problem(artifact_id: str, files: Iterable[str], file_violation: bool, msg: str) -> None:
    PROBLEMS.append(Problem(artifact_id, files, file_violation, msg))


# Windows / Linux / etc os support
if sys.platform == 'win32':
    try:
        # Windows 10 ANSI support
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        EOL = "\033[K\n"
        PROGRESS_EOL = "\033[K\r"
    except AttributeError:
        # Not Windows 10
        EOL = "\n"
        PROGRESS_EOL = "\r"
else:
    EOL = "\033[K\n"
    PROGRESS_EOL = "\033[K\r"

# TODO find a better exception to trap here.
# noinspection PyBroadException
try:
    COLUMN_COUNT, LINE_COUNT = shutil.get_terminal_size(fallback=(-1, -1))
except BaseException:
    COLUMN_COUNT = -1
    LINE_COUNT = -1


# ---------------------------------------------------------------------------
# Configuration Defaults

DEFAULT_CONFIGURATION_FILE_NAME = '.mvn2get.json'
DEFAULT_LOG_LEVEL = LOG_WARN
DEFAULT_REMOTE_REPO_URLS = (
    'https://repo1.maven.org/maven2/',
    'https://www.mvnrepository.com/artifact/',
    'https://plugins.gradle.org/m2/',
)
DEFAULT_PGP_KEY_SERVERS = (
    'hkp://pool.sks-keyservers.net',
    'hkps://hkps.pool.sks-keyservers.net'
)
# If a group ID can't be found, and the artifact starts with this key, then
# use this as the group ID and key replacement.
DEFAULT_MISLABELED_ARTIFACT_GROUP = {
    "org.apache.felix.": ("org.apache.felix", "",),
    "org.osgi.": ("org.osgi", "org.osgi.",),
    "wagon-http-shared": ("org.apache.maven.wagon", "wagon-http-shared",),
}

# ACCEPTABLE LICENSES
#  Use:
#    Licenses that have the license description in the URL must go in the
#    URLS group.  Those that just reference a general "license" url, and just
#    references the project name, should go under the license name, if possible.
DEFAULT_ACCEPTABLE_LICENSE_URLS = (
    # Apache Software License, any version.
    'http://www.apache.org/licenses/',
    
    # Apache Software License, version 1.1
    'http://www.apache.org/licenses/LICENSE-1.1',

    # Apache Software License, version 2
    'http://opensource.org/licenses/apache2.0.php',
    'http://opensource.org/licenses/Apache-2.0',
    'http://www.opensource.org/licenses/apache2.0.php',
    'http://www.apache.org/licenses/LICENSE-2.0',
    'http://www.apache.org/licenses/LICENSE-2.0.txt',
    'http://www.apache.org/license/LICENSE-2.0.txt',
    'http://www.apache.org/licenses/LICENSE-2.0.html',
    'https://www.apache.org/licenses/LICENSE-2.0',
    'http://www.scala-lang.org/downloads/license.html',  # prior to December 2018, this was BSD 3-clause
    'https://www.apache.org/licenses/LICENSE-2.0.txt',
    'https://raw.github.com/jsr107/jsr107spec/master/LICENSE.txt',

    # Apple License
    'http://developer.apple.com/library/mac/#samplecode/AppleJavaExtensions/Listings/README_txt.html#//apple_ref/doc/uid/DTS10000677-README_txt-DontLinkElementID_3',
    
    # BSD (unknown clause count)
    'http://xmlunit.svn.sourceforge.net/viewvc/*checkout*/xmlunit/trunk/xmlunit/LICENSE.txt',
    'http://jdbc.postgresql.org/license.html',
    'http://antlr.org/license.html',
    'http://www.antlr.org/license.html',
    'http://en.wikipedia.org/wiki/BSD_licenses',
    
    # BSD-2-Clause
    'https://jdbc.postgresql.org/about/license.html',
    'http://www.opensource.org/licenses/bsd-license.php',
    'http://www.opensource.org/licenses/bsd-license.html',
    'http://opensource.org/licenses/BSD-2-Clause',
    
    # BSD 3-Clause
    'http://www.scala-lang.org/license.html',
    'http://opensource.org/licenses/BSD-3-Clause',
    'http://asm.ow2.org/license.html',
    'https://asm.ow2.io/license.html',
    'http://asm.objectweb.org/license.html',
    'https://github.com/scodec/scodec-bits/blob/master/LICENSE',
    'https://github.com/sbt/test-interface/blob/master/LICENSE',
    'http://www.antlr.org/license.html',
    'http://jaxen.codehaus.org/license.html',
    # jaxen.codehaus.org license URL is no longer valid, it's now located at:
    'https://github.com/codehaus/jaxen/blob/master/jaxen/LICENSE.txt',

    # New BSD 3-Clause License
    'http://dist.codehaus.org/janino/new_bsd_license.txt',
    'https://github.com/dom4j/dom4j/blob/master/LICENSE',
    'http://www.jcraft.com/jzlib/LICENSE.txt',
    'http://www.jcraft.com/jsch/LICENSE.txt',
    'http://treelayout.googlecode.com/files/LICENSE.TXT',
    
    # The MIT License
    'http://objenesis.googlecode.com/svn/docs/license.html',
    'https://github.com/mockito/mockito/blob/master/LICENSE',
    'http://github.com/mockito/mockito/blob/master/LICENSE',
    'http://code.google.com/p/mockito/wiki/License',
    'http://www.opensource.org/licenses/mit-license.php',
    'http://www.opensource.org/licenses/mit-license.html',
    'http://opensource.org/licenses/MIT',
    'https://opensource.org/licenses/MIT',
    'http://www.opensource.org/licenses/MIT',
    'https://raw.github.com/tatsuhiro-t/argparse4j/master/LICENSE.txt',
    
    # Common Public License Version 1.0
    'http://www.opensource.org/licenses/cpl1.0.txt',
    
    # Bouncy Castle Licence
    # : "Please note this should be read in the same way as the MIT license."
    'http://www.bouncycastle.org/licence.html',
    
    # Mozilla Public License, Version 1.0
    'http://www.mozilla.org/MPL/MPL-1.0.txt',

    # Mozilla Public License, Version 1.1
    'http://www.mozilla.org/MPL/MPL-1.1.html',

    # Mozilla Public License, Version 2.0
    'http://www.mozilla.org/MPL/2.0/index.txt',
    
    # Common Development and Distribution License (CDDL) v1.0, 1.1
    'https://glassfish.dev.java.net/public/CDDLv1.0.html',
    'http://www.sun.com/cddl/cddl.html',
    'http://www.sun.com/cddl',
    'http://repository.jboss.org/licenses/cddl.txt',
    'http://www.opensource.org/licenses/cddl1.php',
    'https://oss.oracle.com/licenses/CDDL+GPL-1.1',
    
    # CDDL + GPLv2 with classpath exception
    'http://glassfish.dev.java.net/nonav/public/CDDL+GPL.html',
    'https://glassfish.dev.java.net/public/CDDL+GPL.html',
    'https://glassfish.dev.java.net/public/CDDL+GPL_1_1.html',
    'https://glassfish.dev.java.net/nonav/public/CDDL+GPL.html',
    'http://glassfish.java.net/public/CDDL+GPL_1_1.html',
    'https://glassfish.java.net/public/CDDL+GPL_1_1.html',
    'https://glassfish.dev.java.net/public/CDDL+GPL_1_1.html',
    'https://glassfish.java.net/nonav/public/CDDL+GPL_1_1.html',
    'http://glassfish.java.net/public/CDDL+GPL.html',
    
    # Eclipse Distribution License - v 1.0
    'http://www.eclipse.org/org/documents/edl-v10.php',
    
    # Eclipse Public License 1.0
    'http://www.eclipse.org/legal/epl-v10.html',
    'http://opensource.org/licenses/eclipse-1.0.php',
    'http://www.spdx.org/licenses/EPL-1.0',
    
    # Eclipse Public License 2.0
    'http://www.eclipse.org/legal/epl-v20.html',
    'https://www.eclipse.org/legal/epl-v20.html',
    'http://www.eclipse.org/legal/epl-2.0',
    'https://www.eclipse.org/org/documents/epl-2.0/EPL-2.0.txt',

    # The PostgreSQL License
    'http://www.postgresql.org/about/licence/',
    
    # WTFPL
    'http://www.wtfpl.net/',
    
    # The JSON License
    'http://json.org/license.html',
    'http://www.json.org/license.html',
    
    # HSQLDB License, similar to BSD-3 Clause
    'http://hsqldb.org/web/hsqlLicense.html',
    
    # Public Domain
    'http://creativecommons.org/licenses/publicdomain',
    'http://www.xmlpull.org/v1/download/unpacked/LICENSE.txt',
    
    # Creative Commons Zero (CC0)
    'http://creativecommons.org/publicdomain/zero/1.0/',
    
    # GNU Lesser General Public License (unversioned)
    'http://www.gnu.org/licenses/lgpl.txt',
    'http://www.gnu.org/licenses/lgpl.html',
    'http://www.gnu.org/copyleft/lesser.html',

    # GNU Lesser General Public License 2.1
    'http://www.gnu.org/licenses/lgpl-2.1.html',
    'https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html',
    
    # GNU Lesser General Public License 3.0
    'http://www.gnu.org/licenses/lgpl-3.0.txt',
    'http://www.gnu.org/licenses/lgpl-2.1.html',
    
    # Mozilla Public License 2.0
    'http://www.mozilla.org/MPL/2.0/',
    
    # Mozilla Public License 2.0 or Eclipse Public License 1.0
    'http://h2database.com/html/license.html',
    
    # Not currently allowed.
    # GNU General Public License (GPL), version 2, with the Classpath exception
    # 'http://openjdk.java.net/legal/gplv2+ce.html',
    # 'https://www.gnu.org/software/classpath/license.html',
    # 'http://repository.jboss.org/licenses/gpl-2.0-ce.txt',
    
    # Not currently allowed.
    # GNU General Public License (GPL)
    # 'http://www.gnu.org/licenses/gpl.txt',
    # 'http://www.gnu.org/licenses/old-licenses/gpl-2.0.html',
    # Generic GNU license doesn't tell us what's what.
    # 'http://www.gnu.org/licenses/licenses.html',

    # Not currently allowed.
    # Gatling Highcharts License
    # https://raw.githubusercontent.com/gatling/gatling-highcharts/master/LICENSE
)
DEFAULT_ACCEPTABLE_LICENSE_NAMES = (
    # Apache License Version 2.0
    'Apache License',
    'Apache License Version 2.0',
    'Apache License, Version 2.0',
    'Apache  Version 2.0, January 2004',
    'The Apache Software License, Version 2.0',
    
    # Public Domain
    'Public Domain',
    
    # A BSD license
    'BSD License (FreeBSD)',
    'BSD',
    'BSD License',
    'The BSD 2-Clause License',
    'The New BSD License',
    
    # BSD-3-Clause
    # see http://jtidy.sourceforge.net/license.html
    # but it is reported as being at an inactive URL:
    #    http://svn.sourceforge.net/viewvc/*checkout*/jtidy/trunk/jtidy/LICENSE.txt?revision=95
    'Java HTML Tidy License',
    
    # MIT License
    'The MIT License',
    'MIT License',
    
    # CDDL licenses.
    'CDDL + GPLv2 with classpath exception',
    'CDDL/GPLv2+CE',
)


# ---------------------------------------------------------------------------
# Configuration

CONFIG = Config()


# ---------------------------------------------------------------------------
# General Constants
FULL_LINK_PATTERN = re.compile(r'<a\s+(.*?)>\s*(.*?)\s*</a>')
HREF_PATTERN = re.compile(r'href\s*=\s*["\'](.*?)["\']')


# ---------------------------------------------------------------------------
# Download File Code
SSL_CONTEXT = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)


def urlopen(url: str) -> Any:
    # urllib.request.urlopen has no formal type...
    if SSL_CONTEXT is None:
        return urllib.request.urlopen(url)
    else:
        return urllib.request.urlopen(url, context=SSL_CONTEXT)


class ToDownload:
    __slots__ = ('url', 'filename', 'overwrite', 'required')

    def __init__(self, url: str, filename: str, overwrite: bool, required: bool) -> None:
        self.url = url
        self.filename = filename
        self.overwrite = overwrite
        self.required = required


def download_artifact(dest_dir: str, artifact_id: str) -> None:
    """
    Base function to download an artifact (as the user specified on the command
    line), with all its files, and perform the necessary checking on that
    artifact.
    """
    warn("{0}".format(artifact_id))
    source_urls = convert_to_repo_urls(artifact_id)
    if not source_urls:
        warn("{0} - skipped".format(artifact_id))
        return
    found = False
    for source_url in source_urls:
        info("{0}".format(source_url))
        dest_path = os.path.join(dest_dir, maven_artifact_path_for_url(source_url))
        if not os.path.isdir(dest_path):
            os.makedirs(dest_path)
        to_download: List[ToDownload] = []
        for filename, required in get_files_in(source_url, dest_dir):
            if is_valid_filename(filename):
                output_file = os.path.join(dest_path, filename)
                file_url = source_url + filename
                to_download.append(ToDownload(file_url, output_file, CONFIG.overwrite, required))
            else:
                info("Skipping file {0} (invalid file)".format(filename))
        if not to_download:
            # Did not find any files in the current URL.
            continue
        found = True
        download_file_list(to_download)
        verify_checksums(artifact_id, dest_path)
        deps = get_required_dependencies(dest_dir, dest_path)
        if CONFIG.recursive:
            for d in deps:
                # Work has already been done to check if the dependency is in
                # local URL or in the download directory.
                info("Downloading required dependency {0} from {1}".format(d, artifact_id))
                download_artifact(dest_dir, d)
        else:
            for d in deps:
                add_problem(artifact_id, [], False, "requires missing dependency {0}".format(d))
    if not found:
        add_problem(artifact_id, [], False, "Did not find any artifact at {0}".format(source_urls))


def download_file_list(artifact_list: List[ToDownload]) -> None:
    """
    Takes a list of dicts (args for download) and
    downloads the files.  This will attempt to use threading to download the
    files in parallel.  The function will return when all the artifacts have
    been downloaded.
    """

    def _da(to_download: ToDownload) -> None:
        info("  -> {0}".format(to_download.url))
        debug("  ---> {0}".format(to_download.filename))
        try:
            progress("downloading {0}".format(to_download.url))
            trace("Downloading {0}".format(to_download.url))
            download(
                to_download.url, to_download.filename, to_download.overwrite,
                show_404=to_download.required
            )
        except BaseException:
            # Assume the download died part-way through.  We can't guarantee
            # that the file was downloaded right.
            delete_file(to_download.filename)
            raise
        # TODO check if the file already exists in local repository.
    
    if CONFIG.can_log(LOG_INFO):
        # Logging requires sequential download
        # Parallel is okay with PROGRESS being on.
        for x in artifact_list:
            _da(x)
    else:
        runners: List[Tuple[Callable[[ToDownload], None], ToDownload]] = []
        for x in artifact_list:
            runners.append((_da, x))
        parallel_jobs(runners)


def download(url: str, filename: str, overwrite: bool, show_errors: bool = True, show_404: bool = True) -> bool:
    """
    Download from the URL to the file.
    """
    if os.path.isfile(filename):
        if overwrite:
            debug("Overwriting existing file {0}".format(filename))
            delete_file(filename)
        else:
            debug("Skipping existing file {0}".format(filename))
            return True
    if not CONFIG.do_remote_download:
        for m_url in CONFIG.remote_repo_urls:
            if url.startswith(m_url):
                return False
    try:
        retry = 3
        last_err: Optional[URLError] = None
        while retry > 0:
            try:
                with open(filename, "wb") as out:
                    progress("connecting to {0}".format(url))
                    with urlopen(url) as inp:
                        progress("downloading from {0}".format(url))
                        if hasattr(inp, 'data'):
                            out.write(inp.data)
                        else:
                            out.write(inp.read())
                return True
            except http.client.IncompleteRead:
                # Connection terminated.  Try again...
                pass
            except URLError as e:
                # If Errno is 11 ("Resource temporarily unavailable"), or
                # -2 ("Name or service unknown")
                # wait a bit and retry...
                if (
                        'Resource temporarily unavailable' not in str(e.reason)
                        and 'Name or service not known' not in str(e.reason)
                ):
                    debug("URL ({1}) error {2}; reason: {0}".format(e.reason, url, e.errno))
                    raise
                time.sleep(1)
                progress("Encountered {0} error.  Waiting to try again: {1}".format(str(e), url[url.rindex('/'):]))
                last_err = e
            retry -= 1
        delete_file(filename)
        if show_errors:
            if last_err:
                add_problem(url, [filename], True, "Failed to download: {0} (too many disconnects)".format(last_err))
            else:
                add_problem(url, [filename], True, "Failed to download (too many disconnects)")
        return False
    except HTTPError as e:
        # Could be a partial download.  Don't keep it.
        delete_file(filename)
        if e.code == 404 or e.code == 308:
            if show_404:
                add_problem(url, [filename], True, "Failed to download: {0}".format(e))
        elif show_errors:
            add_problem(url, [filename], True, "Failed to download: {0}".format(e))
        return False
    except URLError as e:
        # Could be a partial download.  Don't keep it.
        delete_file(filename)
        if show_errors:
            add_problem(url, [filename], True, "Incorrectly constructed URL")
            raise e
        return False
    except BaseException:
        # Could be a partial download.  Don't keep it.
        delete_file(filename)
        warn("Error downloading {0} into {1}".format(url, filename))
        raise


def get_files_in(url: str, outdir: str) -> List[Tuple[str, bool]]:
    """
    Load the maven repo page for the URL (it should be the directory for the
    artifact), and parse the HTML that lists the files.  There might be a
    more programatic way to do this.
    """
    outfile = os.path.join(
        tmpdir(outdir),
        url.replace(':', '_').replace('/', '_').replace('?', '_').replace('+', '_')
    )
    if not download(url=url, filename=outfile, overwrite=False, show_errors=True, show_404=False):
        return []
    with open(outfile, 'rb') as f:
        progress("reading from {0}".format(outfile))
        page = f.read().decode('utf-8')
    ret: List[str] = []
    for a_tag_attributes, display_text in FULL_LINK_PATTERN.findall(page):
        # display_text may not show the real link.
        href = HREF_PATTERN.search(a_tag_attributes)
        if href:
            file_url = href.group(1)
            if not file_url:
                continue
            # Some repositories put extra junk in front of the link.
            while file_url[0] in '/:':
                file_url = file_url[1:]
            if file_url and not file_url.startswith('..'):
                # Just the name of the file; no URL.
                ret.append(file_url)

    # Some repos do not list the checksum and PGP signatures.
    # Explicitly add these to the list.
    final_ret: List[Tuple[str, bool]] = []
    for file_url in ret:
        final_ret.append((file_url, True,))
        for ext in VERIFY_FILE_EXTENSIONS:
            if file_url.endswith(ext):
                continue
            extended = file_url + ext
            if extended in ret:
                continue
            # We're guessing that this file exists, so therefore it's not required.
            final_ret.append((extended, False,))

    return final_ret


def parallel_jobs(callable_list: List[Tuple[Callable[[ToDownload], None], ToDownload]]) -> None:
    problems: List[BaseException] = []
    waiter = threading.Barrier(len(callable_list) + 1)

    def _x(index: int, r: Callable[[ToDownload], None], p: List[BaseException], a: ToDownload) -> None:
        try:
            trace("Starting {0}".format(index))
            r(a)
            trace("Ended {0}".format(index))
        except BaseException as e:
            warn("Exception in {0}: {1}".format(index, e))
            p.append(e)
        finally:
            waiter.wait()
            trace("Barrier finished for {0}".format(index))

    i = 0
    for callback, arg in callable_list:
        t = threading.Thread(
            target=_x, args=(i, callback, problems, arg), daemon=None
        )
        t.start()
        i += 1
    waiter.wait()
    if len(problems) > 0:
        raise problems[0]


# ---------------------------------------------------------------------------
# Maven 2 Repository Layout

def maven_artifact_path_for_url(url: str) -> str:
    """Get the artifact path for the given maven repo URL."""
    for prefix in CONFIG.remote_repo_urls:
        if url.startswith(prefix):
            return os.path.normpath(url[len(prefix):])
    raise ValueError('unknown artifact url ' + str(url))


def convert_to_repo_urls_from_url(src_url: str) -> List[str]:
    """Heuristic to convert a URL into remote maven repo URLs."""
    for base_url in [*CONFIG.remote_repo_urls, *CONFIG.local_repo_urls]:
        if not src_url.startswith(src_url):
            continue
        parts = src_url[len(base_url):].split('/')
        if parts[-1].endswith(".jar") or parts[-1].endswith(".pom"):
            # User could specify a jar or pom artifact, rather than the path.
            parts = parts[:-1]
        if parts[0].find('.') > 0:
            # Some repositories, such as mvnrepository.com, use periods instead of slashes
            # for separators in the group name.
            parts = [*parts[0].split('.'), *parts[1:]]
        ret: List[str] = []
        for prefix in CONFIG.remote_repo_urls:
            repo_url = prefix + "/".join(parts)
            if not repo_url[-1] == '/':
                repo_url += '/'
            ret.append(repo_url)
        return ret

    add_problem(src_url, [], False, "Unknown source repository.")
    return []


def convert_to_repo_urls(artifact_id: str) -> List[str]:
    if artifact_id.startswith("http://") or artifact_id.startswith("https://"):
        return convert_to_repo_urls_from_url(artifact_id)
    if artifact_id.count(':') == 2:
        return convert_to_repo_urls_from_artifact(artifact_id)
    add_problem(
        artifact_id, [], False,
        "Unknown format artifact format.  Must be either a maven repo URL or group:artifact:version"
    )
    return []


def convert_to_repo_urls_from_artifact(aid: str, use_version: bool = True) -> List[str]:
    fmt = use_version and "{0}{1}/{2}/{3}/" or "{0}{1}/{2}/"
    parts = aid.split(':')
    path = parts[0].replace('.', '/')
    ret = []
    for base_url in CONFIG.remote_repo_urls:
        ret.append(fmt.format(base_url, path, parts[1], parts[2]))
    return ret


# ---------------------------------------------------------------------------
# Artifact file validation

VERIFY_FILE_EXTENSIONS = ('.md5', '.sha1', '.asc', '.md5.asc', '.sha1.asc', '.asc.md5', '.asc.sha1',)


def verify_checksums(artifact_id: str, dest_path: str) -> None:
    """Perform appropriate verification for the downloaded files."""
    for filename in os.listdir(dest_path):
        if not (filename.endswith('.sha1') or filename.endswith('.md5')):
            path = os.path.join(dest_path, filename)
            verify_checksum(artifact_id, path, 'md5')
            verify_checksum(artifact_id, path, 'sha1')
        
        # Note: no 'else', because .asc files can have checksums.
        if filename.endswith('.asc'):
            base_file = os.path.join(dest_path, filename[:-4])
            if os.path.isfile(base_file):
                verify_pgp(artifact_id, base_file, os.path.join(dest_path, filename))
            else:
                debug(
                    " - Downloaded asc file ({0}) with no corresponding signed file (expected {1})".format(
                        filename, base_file
                    )
                )


def verify_checksum(artifact_id: str, path: str, hash_name: str) -> None:
    """Verify the hash of the source file."""
    ck_file = path + '.' + hash_name
    if os.path.isfile(ck_file):
        progress("verify {0} {1}".format(hash_name, path))
        with open(ck_file, "r") as ft:
            # Sometimes the file can have newlines at the end, or can be in
            # the format 'sha1code   filename'
            # but it can also be 'MD5(md5code) filename'
            ck_parts = ft.read().strip().split(' ')
            if len(ck_parts) > 1 and ck_parts[0].lower().startswith(hash_name + '('):
                ck_expected = ck_parts[1]
            else:
                ck_expected = ck_parts[0]
        ck = hashlib.new(hash_name)
        with open(path, "rb") as fb:
            ck.update(fb.read())
        if ck.hexdigest() != ck_expected:
            add_problem(
                artifact_id, [path], True, "{0} {3} does not match downloaded checksum file ({1} vs {2})".format(
                    path, ck.hexdigest(), ck_expected, hash_name
                )
            )
    elif not path.endswith('.asc'):
        # .asc files *should* have a checksum, but often they don't.
        info("  !> {0} has no {1} file".format(os.path.basename(path), hash_name))


def verify_pgp(artifact_id: str, src_file: str, signature_file: str) -> None:
    if GPG_INST is None or not CONFIG.pgp_key_servers or CONFIG.no_pgp:
        debug(" - skipped PGP signature checking of {0}".format(src_file))
        return
    
    progress("verify pgp {0}".format(src_file))
    with open(signature_file, 'rb') as f:
        verify = GPG_INST.verify_file(f, src_file)
    # username, key_id, signature_id, fingerprint, trust_level and trust_text
    if verify.status == 'no public key':
        # Load the public key and try again
        debug(" - loading public key {0}".format(verify.key_id))
        for key_server in CONFIG.pgp_key_servers:
            GPG_INST.recv_keys(key_server, verify.key_id)
        with open(signature_file, 'rb') as f:
            verify = GPG_INST.verify_file(f, src_file)
    if verify.valid:
        info("  ~> PGP signature valid for {0}".format(src_file))
        debug("  -- key id: {0}, sig id: {1}, fingerprint: {2}, trust: {3}".format(
            verify.key_id, verify.signature_id, verify.fingerprint, verify.trust_text))
    elif verify.status.lower() == 'no public key':
        add_problem(
            artifact_id, [src_file, signature_file], True,
            "PGP signature could not be validated for {0}: {1}".format(src_file, verify.status)
        )
    elif verify.status.lower() == 'signature bad':
        # Signature in the file is bad, not a failed validation.
        add_problem(
            artifact_id, [signature_file], True,
            "PGP signature validation failed for {0}: signature file is corrupted".format(src_file)
        )
    elif verify.status.lower() != 'signature valid':
        add_problem(
            artifact_id, [src_file, signature_file], True,
            "PGP signature validation failed for {0}: {1}".format(src_file, verify.status)
        )
    else:
        info("  !> PGP signature not valid, but valid?")


# ---------------------------------------------------------------------------
# POM loading

def get_required_dependencies(outdir: str, path: str) -> List[str]:
    progress("loading pom file {0}".format(path))
    pom = find_downloaded_pom_file(path)
    if pom is None:
        info("  !> {0} has no pom file".format(path))
        return []
    debug("loaded pom {0}".format(pom.decl.id()))
    
    ret = []
    for p in pom.parent_dependencies:
        parent = load_parent_pom_tree(outdir, pom, p)
        if parent is None:
            continue
        if parent.missing:
            ret.append(parent.decl.id())
    for d in pom.dependencies:
        if d.optional or d.is_test:
            # Skip the dependency
            debug("skipping optional or test dependency {0}".format(d.id()))
            continue
        progress("loading dependent version info for {0}".format(d.id()))
        load_version_info(outdir, d)
        if d.is_vague_version():
            debug("skipping vague version for dependency {0}".format(d.id()))
            continue
        progress("loading dependent pom {0}".format(d.id()))
        if not d.group_id:
            if not pom.decl.group_id:
                warn("Dependent ({0}) has no group, and current ({1}) has no group".format(d.id(), pom.decl.id()))
            d.group_id = pom.decl.group_id
        if d.group_id == '${pom.groupId}':
            # group not defined; might be a mis-labeled artifact.
            for mislabeled_group, group_art_replace in CONFIG.mislabeled_artifact_groups:
                if d.artifact_id.startswith(mislabeled_group):
                    old_id = d.id()
                    d.group_id = group_art_replace[0]
                    d.artifact_id = group_art_replace[1] + d.artifact_id[len(mislabeled_group) + 1:]
                    warn("Dependent ({0}) of ({1}) has no group, but is using a mislabeled artifact; using {2}".format(
                        old_id, pom.decl.id(), d.id()
                    ))
                    break
        dp = load_pom_file(outdir, d)
        if dp is None:
            add_problem(
                pom.decl.id(), [], False,
                "Could not find declared dependency {0}".format(d.id())
            )
            continue
        if dp.missing:
            ret.append(dp.decl.id())
    
    return ret


def load_version_info(outdir: str, dependency: 'Dependency') -> bool:
    """check the maven-metadata.xml file for the version number."""
    meta = MavenMetaFile(outdir, dependency)
    best = dependency.version_range.best_fit(meta)
    if best is None:
        info("  !> Unable to determine version number for declared dependency {0}".format(dependency.id()))
        debug("  !> known version {0}, range {1}".format(dependency.version, dependency.version_range))
        return False
    old_version = dependency.version
    dependency.version = best.version
    dependency.version_range.explicit_value = True
    if dependency.version != old_version:
        info("  %> Set best-fit version for {0} (was {1})".format(dependency.id(), old_version))
    # Note: not deleting the temp file.
    
    return not dependency.is_vague_version()


class License:
    __slots__ = ('name', 'url',)

    def __init__(self, name: str, url: str) -> None:
        self.name = name
        self.url = url

        
class PomFile(object):
    parent_dependencies: List['Dependency']
    licenses: List[License]
    dep_reference: List['Dependency']
    dependencies: List['Dependency']

    def __init__(self, filename: str, ref_dependency: Optional['Dependency']) -> None:
        self.file = os.path.basename(filename)
        self.missing = False
        self.valid = True
        self.licenses = []
        self.parent_dependencies = []
        self.dep_reference = []
        self.dependencies = []

        pom_dom = parse_xml(filename)

        self.decl = Dependency(pom_dom.getElementsByTagName('project')[0])
        if self.decl.has_no_group:
            # Make a guess based on the source dependency
            if ref_dependency is None:
                debug("No group defined for pom file {0}".format(filename))
            else:
                self.decl.group_id = ref_dependency.group_id
        if self.decl.is_vague_version():
            # Make a guess based on the source dependency
            if ref_dependency is None:
                debug("No version defined for pom file {0}".format(filename))
            else:
                debug("loading version {0} into {1}".format(ref_dependency.version, self.decl.id()))
                self.decl.version = ref_dependency.version
                self.decl.version_range = ref_dependency.version_range
            
        self.properties = pom_get_properties(pom_dom)
        
        # For now, pom license parsing is internal.
        # Should be moved outside of this, so that license issues invalidate the whole artifact.
        acceptable_count = 0
        unacceptable = []
        for el in pom_dom.getElementsByTagName('license'):
            lic = License(
                xml_getnode_text(el, 'name').strip(),
                xml_getnode_text(el, 'url').strip()
            )
            self.licenses.append(lic)
            found_lic = False
            if len(lic.url) > 0:
                for n in CONFIG.acceptable_license_urls:
                    if check_license_url(lic.url, n):
                        acceptable_count += 1
                        found_lic = True
                        break
            if not found_lic and len(lic.name) > 0:
                for n in CONFIG.acceptable_license_names:
                    if check_license_name(lic.name, n):
                        acceptable_count += 1
                        found_lic = True
                        break
            if not found_lic:
                unacceptable.append("{0} ({1})".format(lic.name, lic.url))
        if len(self.licenses) <= 0:
            if not CONFIG.allow_no_license:
                add_problem(
                    self.decl.id(), [self.file], True,
                    'No license declared in violation of license restriction.'
                )
                self.valid = False
            else:
                add_problem(
                    self.decl.id(), [self.file], False,
                    'No license declared.'
                )
        elif acceptable_count <= 0:
            if not CONFIG.allow_unacceptable_licenses:
                add_problem(
                    self.decl.id(), [self.file], True,
                    'Not an acceptable license ({0}) in violation of license restriction'.format(
                        ', '.join(unacceptable)
                    )
                )
                self.valid = False
            else:
                add_problem(
                    self.decl.id(), [self.file], False,
                    'Not an acceptable license ({0})'.format(', '.join(unacceptable))
                )

        # Make sure we only grab this pom's parent, and not some weird other place.
        for el in xml_getnodes(pom_dom, 'parent'):
            parent = Dependency(el)
            if self.decl.id() == parent.id():
                warn("{0} declares itself as a parent.".format(parent.id()))
                continue
            self.parent_dependencies.append(parent)
            if parent.has_no_group:
                if not self.decl.group_id:
                    warn("Parent ({1}) of {0} has no group, and current ({2}) has no group".format(
                        filename, parent.id(), self.decl.id()
                    ))
                parent.group_id = self.decl.group_id
            elif self.decl.has_no_group:
                self.decl.group_id = parent.group_id
            if parent.is_vague_version():
                parent.version = self.decl.version
                parent.version_range = self.decl.version_range
            elif self.decl.version is None or len(self.decl.version) <= 0:
                self.decl.version = parent.version
                self.decl.version_range = parent.version_range
                self.properties = pom_get_properties(pom_dom)
        
        for dep_group in xml_getnodes(pom_dom, 'dependencyManagement'):
            for deps in xml_getnodes(dep_group, 'dependencies'):
                debug("Checking dependency management section")
                for el in deps.getElementsByTagName('dependency'):
                    d = Dependency(el)
                    self.dep_reference.append(d)
                    if CONFIG.include_dep_management:
                        self.dependencies.append(d)
                    debug("Loading properties for dm/d/dependency {0}".format(d.id()))
                    d.for_properties(self.properties, False)
                    debug(" - dependency now {0}".format(d.id()))
                    if d.has_no_group:
                        if not self.decl.group_id:
                            warn("Parent ({1}) of {0} has no group, and self ({2}) has no group".format(
                                filename, d.id(), self.decl.id()
                            ))
                        d.group_id = self.decl.group_id
                    # Do not force the dependency version.
                    # if d.version is None or len(d.version) <= 0:
                    #     d.version = self.decl.version
                    #     d.version_range = self.decl.version_range
                    
        # Cannot just check for elements named 'dependencies', because that
        # can pick up plugin dependencies, which we don't care about.
        for deps in xml_getnodes(pom_dom, 'dependencies'):
            for el in deps.getElementsByTagName('dependency'):
                d = Dependency(el)
                # Check if the dependency is in the list of references.
                for ref_def in self.dep_reference:
                    if ref_def.group_id == d.group_id and ref_def.artifact_id == d.artifact_id:
                        debug("Inheriting information from {0}".format(ref_def.id()))
                        if d.version is None or d.version == '':
                            d.version = ref_def.version
                            d.version_range = MavenVersionRange(d.version)
                
                self.dependencies.append(d)
                debug("Loading properties for dependency {0}".format(d.id()))
                d.for_properties(self.properties, False)
                if d.has_no_group:
                    if not self.decl.group_id:
                        warn(
                            "Parent ({1}) of dependency {0} has no group, "
                            "and current dependency ({2}) has no group".format(
                                filename, d.id(), self.decl.id()
                            )
                        )
                    d.group_id = self.decl.group_id
                debug("=== Dependency from {0}: {1}".format(self.decl.id(), d.id()))
                # Do not force the dependency version.
                # if d.version is None or len(d.version) <= 0:
                #     d.version = self.decl.version
                #     d.version_range = self.decl.version_range

    def has_parent(self, decl: 'Dependency') -> bool:
        for p in self.parent_dependencies:
            if p.id() == decl.id():
                return True
        return False

    def for_parent_pom(self, parent_pom: 'PomFile') -> None:
        if not self.decl.group_id and parent_pom.decl.group_id:
            self.decl.group_id = parent_pom.decl.group_id
        debug("Adding parent properties into {0} from {1}".format(self.decl.id(), parent_pom.decl.id()))
        self.dep_reference.extend(parent_pom.dep_reference)
        for p in self.parent_dependencies:
            p.for_properties(parent_pom.properties, True)
        for d in self.dependencies:
            # Check if the dependency is in the list of references.
            for ref_def in self.dep_reference:
                if ref_def.group_id == d.group_id and ref_def.artifact_id == d.artifact_id:
                    debug("Inheriting information from {0}".format(ref_def.id()))
                    if d.version is None or d.version == '':
                        d.version = ref_def.version
                        d.version_range = MavenVersionRange(d.version)
            d.for_properties(parent_pom.properties, False)
        if self.decl.version is None or len(self.decl.version) <= 0:
            self.decl.version = parent_pom.decl.version
            self.decl.version_range = parent_pom.decl.version_range
        # Inherit properties.
        for k, v in parent_pom.properties.items():
            if k not in self.properties:
                self.properties[k] = v
        self.properties['project.parent.groupId'] = parent_pom.decl.group_id
        self.properties['project.parent.version'] = parent_pom.decl.version
        debug("Final properties for {0}: {1}".format(self.decl.id(), repr(self.properties)))

    
def find_downloaded_pom_file(dirname: str) -> Optional[PomFile]:
    pom_files = []
    for f in os.listdir(dirname):
        if f.endswith('.pom'):
            pom_files.append(f)
    if len(pom_files) > 1:
        # A few libraries include pom files for the sources and jars.
        # So try the files that only end in the output directory + extension.
        while dirname.endswith('/') or dirname.endswith('\\'):
            dirname = dirname[0:-1]
        ending = '-' + os.path.basename(dirname) + '.pom'
        debug(" - multiple detected pom files; refining search for files in {0} ending with {1}".format(
            dirname, ending
        ))
        old = pom_files
        pom_files = []
        for f in old:
            if f.endswith(ending):
                pom_files.append(f)
    if len(pom_files) != 1:
        return None
    return PomFile(os.path.join(dirname, pom_files[0]), None)


def pom_get_properties(pom_dom: xml.dom.minidom.Document) -> Dict[str, str]:
    ret: Dict[str, str] = {}
    root_el = pom_dom.getElementsByTagName('project')[0]
    ret['project.groupId'] = xml_getnode_text(root_el, 'groupId')
    ret['project.artifactId'] = xml_getnode_text(root_el, 'artifactId')
    ret['project.version'] = xml_getnode_text(root_el, 'version')
    for prop_el in root_el.getElementsByTagName('properties'):
        for key_el in prop_el.childNodes:
            if key_el.nodeType == key_el.ELEMENT_NODE:
                key = key_el.tagName
                value = xml_gettext(key_el)
                ret[key] = value
    return ret
    

class Dependency:
    def __init__(self, el: xml.dom.minidom.Element) -> None:
        object.__init__(self)
        self.__el = el
        self.artifact_id = xml_getnode_text(el, 'artifactId')
        self.group_id = xml_getnode_text(el, 'groupId')
        if not self.artifact_id and self.group_id.find('.') > 0:
            parts = self.group_id.split('.')
            self.artifact_id = '.'.join(parts[:-1])
            self.group_id = parts[-1]
        self.version = xml_getnode_text(el, 'version')
        self.version_range = MavenVersionRange(self.version)
        # ignore 'classifier'
        self.optional_text = xml_getnode_text(el, 'optional')
        self.scope = xml_getnode_text(el, 'scope')
        self.optional = self.optional_text == 'true'
        # is_test isn't really precise in its meaning anymore, but it works enough
        # for checking if the scope means it should be ignored.
        self.is_test = 'test' == self.scope or 'provided' == self.scope
    
    @property
    def has_no_group(self) -> bool:
        return len(self.group_id.strip()) <= 0
    
    def is_vague_version(self) -> bool:
        return self.version is None or len(self.version) <= 0 or self.version_range.is_vague()
    
    def id(self) -> str:
        return '{0}:{1}:{2}'.format(self.group_id, self.artifact_id, self.version)
    
    def path(self) -> str:
        return '{0}/{1}/{2}'.format(self.group_id.replace('.', '/'), self.artifact_id, self.version)
    
    def pom_path(self) -> str:
        return '{0}/{1}/{2}/{1}-{2}.pom'.format(self.group_id.replace('.', '/'), self.artifact_id, self.version)
    
    def for_properties(self, props: Mapping[str, str], is_parent: bool) -> None:
        orig_version = self.version
        self.artifact_id = self.__rep(self.artifact_id, props)
        self.group_id = self.__rep(self.group_id, props)
        
        # Very, very important rule.  If the group id from the owning pom props
        # matches this group ID, or if the props come from the parent, then
        # allow for replacing the version number.  Otherwise, it can cause an
        # issue where we expect the version to be the latest version.
        debug(" - Original version for {1}: {0}; properties: {2}".format(self.version, self.id(), repr(props)))
        if (
                (is_parent or (self.group_id == props['project.groupId']))
                and (self.version is None or len(self.version) <= 0)
        ):
            self.version = props['project.version']
        self.version = self.__rep(self.version, props)
        debug(" - Prop replaced version for {1}: {0}".format(self.version, self.id()))
        self.version_range = MavenVersionRange(self.version)
        if orig_version != self.version:
            trace("{0}: replaced version from {1}".format(self.id(), orig_version))
        elif self.version is None or len(self.version) <= 0:
            debug("{0}: no version information after replacement from {1}".format(self.id(), repr(props)))
    
    def __rep(self, value: str, props: Mapping[str, str]) -> str:
        before = None
        while before != value:
            before = value
            for k, v in props.items():
                value = value.replace('${' + k + '}', v)
        return value


LOADED_PARENT_POMS_CACHE: Dict[str, PomFile] = {}


def load_pom_file(outdir: str, dependency: Dependency) -> Optional[PomFile]:
    assert isinstance(dependency, Dependency)

    path = dependency.pom_path()

    # First see if it's been downloaded.
    pom_file = os.path.join(outdir, path)
    if os.path.isfile(pom_file):
        debug("  %> Loading local pom file {0} for {1}".format(pom_file, dependency.id()))
        try:
            ret = PomFile(pom_file, dependency)
            info("  *> Using local repo pom file {0} for {1}".format(pom_file, dependency.id()))
            return ret
        except ExpatError as e:
            add_problem(pom_file, [pom_file], True, "Failed to parse POM file {0}".format(pom_file))
            info("  !> Failed to parse {0}: {1}".format(pom_file, repr(e)))
            return None

    tf = os.path.join(tmpdir(outdir), os.path.basename(path))
    if os.path.isfile(tf):
        debug("  %> Loading cached pom file {0} for {1}".format(tf, dependency.id()))
        try:
            ret = PomFile(tf, dependency)
            # The only way that this is valid is if the file was downloaded
            # from a local repo, meaning that it is a known-to-exist-so-don't-download artifact.
            if not os.path.isfile(tf + '..local'):
                ret.missing = True
            info("  *> Using cached temp dependency {0}".format(dependency.id()))
            # Note: not removing the temp file, for restart performance.
            # delete_file(tf)
            return ret
        except ExpatError as e:
            add_problem(
                tf, [pom_file, tf], True,
                "Failed to parse cached POM file"
            )
            info("  !> Failed to parse {0}: {1}".format(tf, repr(e)))
            # Keep the file around for debugging
            return None

    # Try to download it, first from the local repo, then from
    # the remote depot (which will require an additional download because it's
    # missing from the local depot).
    if CONFIG.check_in_local:
        for base_url in CONFIG.local_repo_urls:
            file_url = base_url + path
            if download(url=file_url, filename=tf, overwrite=True, show_errors=False, show_404=False):
                debug("Downloaded {0} to temporary file {1}".format(file_url, tf))
                try:
                    ret = PomFile(tf, dependency)
                    info("  *> Using local repo dependency {0}".format(dependency.id()))
                    # Mark this as an local dependency
                    with open(tf + '..local', 'w') as f:
                        f.write("Downloaded from local repo")
                    return ret
                except ExpatError as e:
                    add_problem(
                        pom_file, [pom_file, tf], True,
                        "Failed to parse POM file {0}".format(tf)
                    )
                    info("  !> Failed to parse {0}: {1}".format(tf, repr(e)))
                    # Keep the file around for debugging
                    return None
    for base_url in CONFIG.remote_repo_urls:
        file_url = base_url + path
        if download(url=file_url, filename=tf, overwrite=True, show_errors=False, show_404=False):
            info("  ?> Found missing dependency {0}".format(dependency.id()))
            try:
                ret = PomFile(tf, dependency)
            except ExpatError as e:
                add_problem(
                    pom_file, [pom_file, tf], True,
                    "Failed to parse POM file {0}".format(tf)
                )
                info("  !> Failed to parse {0}: {1}".format(tf, repr(e)))
                # Keep the file around for debugging
                return None
            delete_file(tf)
            ret.missing = True
            return ret
        # Note: not removing the temp file, for restart performance.
        # delete_file(tf)
    return None


def load_parent_pom_tree(outdir: str, child: PomFile, dependency: Dependency) -> Optional[PomFile]:
    debug("loading parent pom {0}".format(dependency.id()))
    progress("loading parent pom {0}".format(dependency.id()))
    global LOADED_PARENT_POMS_CACHE
    parent: PomFile
    if dependency.id() in LOADED_PARENT_POMS_CACHE:
        # Prevent recursion when the parent graph contains a cycle.
        parent = LOADED_PARENT_POMS_CACHE[dependency.id()]
    else:
        opt_parent = load_pom_file(outdir, dependency)
        if opt_parent is None:
            add_problem(
                child.decl.id(), [], False,
                "Could not find declared parent {0}".format(dependency.id())
            )
            return None
        parent = opt_parent
        LOADED_PARENT_POMS_CACHE[dependency.id()] = parent
        for p in parent.parent_dependencies:
            load_parent_pom_tree(outdir, parent, p)
    child.for_parent_pom(parent)
    return parent


QUALIFIER_ORDER = ("alpha", "beta", "milestone", "rc", "snapshot")


class MavenVersion(object):
    # See https://maven.apache.org/pom.html#Dependency_Version_Requirement_Specification

    tokens: List[Tuple[bool, str]]

    def __init__(self, version_number: str) -> None:
        self.version = version_number.strip()
        self.tokens = []
        if len(version_number) > 0:
            # initialize our buffer
            buff = '-'
            state = 0
            for c in version_number:
                if c.isspace():
                    # ignore whitespace
                    continue
                if state == 0:
                    # start of a token.  buff should contain a '.' or '-'.
                    if c == '.':
                        # implied '0.'; this handles the "prefix" part of comparison
                        self.tokens.append((True, buff + '0',))
                        buff = c
                        state = 0
                    elif c == '+':
                        # invalid version format, but it's used by
                        # com/github/rholder/guava-retrying/1.0.6.
                        buff += '0'
                        state = 1
                    elif c in '.-[](),+':
                        raise Exception('Invalid version number format {0}'.format(version_number))
                    else:
                        buff += c
                        if c.isdigit():
                            state = 1
                        else:
                            state = 2
                elif state == 1:
                    # middle of a numeric token.
                    if c in '.-':
                        self.tokens.append((True, buff,))
                        buff = c
                        state = 0
                    elif c.isdigit():
                        buff += c
                    else:
                        # transition between digits and chars
                        self.tokens.append((True, buff,))
                        buff = '-' + c
                        state = 2
                elif state == 2:
                    # middle of a character token.  character tokens are
                    # case insensitive
                    if c in '.-':
                        # ignore 'final' and 'ga' markers - they are equal to
                        # empty.
                        buff = buff.lower()
                        if buff[1:] not in ('final', 'ga'):
                            self.tokens.append((False, buff,))
                        buff = c
                        state = 0
                    # elif buff == 'v' and c.isdigit():
                    #     # The format is "v123", so have a special case for this one.
                    #     buff += c
                    #     state = 3
                    elif c.isdigit():
                        # transition between digits and chars
                        # ignore 'final' and 'ga' markers - they are equal to
                        # empty.
                        buff = buff.lower()
                        if buff[1:] not in ('final', 'ga'):
                            self.tokens.append((False, buff,))
                        buff = '-' + c
                        state = 1
                    else:
                        buff += c
                elif state == 3:
                    # In the middle of a "v1234" style version identifier.
                    # It will be considered a text token for comparison sake,
                    # but will only allow numbers at this point.
                    if c in '.-':
                        self.tokens.append((True, buff,))
                        buff = c
                        state = 0
                    elif c.isdigit():
                        buff += c
                    else:
                        # transition between digits and chars
                        self.tokens.append((True, buff,))
                        buff = '-' + c
                        state = 2
                    
            if len(buff) > 1:
                # > 1 because if it's only the first '.' or '-' then it's not a token
                if state == 1:
                    self.tokens.append((True, buff,))
                elif state == 2:
                    buff = buff.lower()
                    if buff[1:] not in ('final', 'ga'):
                        self.tokens.append((False, buff,))
    
    def __eq__(self, that: object) -> bool:
        if isinstance(that, MavenVersion):
            return self.compare(that) == 0
        return False

    def __ne__(self, that: object) -> bool:
        return not(self.__eq__(that))
    
    def __repr__(self) -> str:
        t = []
        for sn, st in self.tokens:
            t.append(st)
        return "".join(t)
    
    def __str__(self) -> str:
        r = repr(self)
        if len(r) <= 1:
            return "?"
        return r[1:]

    def compare(self, that: 'MavenVersion') -> int:
        """ returns == 0 if equal, < 0 if self later than that, or > 0 if self earlier than that """
        if self.version == that.version:
            return 0
        if that is None or len(that.version) <= 0:
            return -1
        if self.version is None or len(self.version) <= 0:
            return 1
        
        for index in range(0, min(len(self.tokens), len(that.tokens))):
            sn, sv = self.tokens[index]
            tn, tv = that.tokens[index]
            if sn == tn and sv == tv:
                continue
            
            # ".qualifier" < "-qualifier" < "-number" < ".number"
            if sn and not tn:
                # self is numeric, that is not-numeric
                return -1
            if tn and not sn:
                # self is not-numeric, that is numeric
                return 1
            # sn and tn are equal
            if sv[0] == '.' and tv[0] == '-':
                if sn:
                    # self is '.number', that is '-number'
                    return -1
                else:
                    # self is '.qualifier', that is '-qualifier'
                    return 1
            if sv[0] == '-' and tv[0] == '.':
                if sn:
                    # self is '-number', that is '.number'
                    return 1
                else:
                    # self is '-qualifier', that is '.qualifier'
                    return -1
            # self and that both start with the same . or -
            if sn:
                # numeric; natural order
                return int(tv[1:]) - int(sv[1:])
            else:
                # qualifier
                # "alpha" < "beta" < "milestone" < "rc" = "cr" < "snapshot" < "" = "final" = "ga" < "sp"
                # Note that 'final' and 'ga' have already been omitted
                if sv[1:] == 'cr':
                    sv = sv[0] + 'rc'
                if tv[1:] == 'cr':
                    tv = tv[0] + 'rc'
                if sv == tv:
                    # cr -> rc conversion happened
                    continue
                if sv in QUALIFIER_ORDER:
                    if tv in QUALIFIER_ORDER:
                        si = QUALIFIER_ORDER.index(sv)
                        ti = QUALIFIER_ORDER.index(tv)
                        assert si != ti
                        return ti - si
                    else:
                        # tv is a custom qualifier, which isn't as important.
                        return -1
                if tv in QUALIFIER_ORDER:
                    # sv is a custom qualifier, which isn't as important
                    return 1
                assert sv != tv
                return sv > tv and -1 or 1
        
        # All the tokens were equal up to the shortest length of the two pairs.
        # If one of them has one of the qualifiers that's incremental, then ignore it.
        if len(self.tokens) == len(that.tokens):
            return 0
        if len(self.tokens) > len(that.tokens):
            sn, sv = self.tokens[len(that.tokens)]
            if not sn and sv[1:] in ('alpha', 'beta', 'milestone', 'cr', 'rc', 'snapshot'):
                return 1
            # Otherwise self is more specific
            return -1
        tn, tv = that.tokens[len(self.tokens)]
        if not tn and tv[1:] in ('alpha', 'beta', 'milestone', 'cr', 'rc', 'snapshot'):
            return -1
        # Otherwise that is more specific
        return 1


class MavenMetaFile(object):
    versions: List[MavenVersion]
    releases: List[MavenVersion]

    def __init__(self, outdir: str, dependency: Dependency):
        self.versions = []
        self.releases = []
        
        meta_urls = [(mu + 'maven-metadata.xml') for mu in convert_to_repo_urls_from_artifact(dependency.id(), False)]
        tf = os.path.join(
            tmpdir(outdir),
            '{0}-{1}-maven-metadata.xml'.format(dependency.group_id, dependency.artifact_id)
        )
        found = False
        for meta_url in meta_urls:
            if download(url=meta_url, filename=tf, overwrite=False):
                try:
                    v_dom = parse_xml(tf)
                    for el in v_dom.getElementsByTagName('version'):
                        v = xml_gettext(el).strip()
                        if len(v) > 0:
                            self.versions.append(MavenVersion(v))
                    for el in v_dom.getElementsByTagName('release'):
                        v = xml_gettext(el).strip()
                        if len(v) > 0:
                            self.releases.append(MavenVersion(v))
                    found = True
                    break
                except ExpatError as e:
                    add_problem(
                        meta_url, [tf], True,
                        "Invalid metadata file {0}".format(tf)
                    )
                    debug(" --- downloaded into {0}; parse error {1}".format(tf, e))
            
                # Note: not deleting the temp file.
        if not found:
            info("  *> Could not find metadata.xml file for {0} ({1})".format(dependency.id(), meta_urls))


class MavenVersionRange(object):
    version_sets: List[Tuple[str, str, MavenVersion, MavenVersion]]

    def __init__(self, version_number: str) -> None:
        assert isinstance(version_number, str)
        self.explicit_value = False
        self.version = (version_number or "").strip()
        self.version_sets = []
        # each version set entry is a tuple of (min_type, max_type, v0, v1)
        # where *_type is '(', '[', or ''
        # and v* is a MavenVersion.
        search = 0
        v = version_number
        vs = []
        while search >= 0:
            p0 = v.find('],')
            p1 = v.find('),')
            search = max(p0, p1)
            if p0 > 0 and (p1 < 0 or p0 < p1):
                vs.append(v[0:p0+1])
                v = v[p0+2:]
            elif p1 > 0 and (p0 < 0 or p1 < p0):
                vs.append(v[0:p1+1])
                v = v[p1+2:]
        if len(v) > 0:
            vs.append(v)
        
        for v in vs:
            if v[0] == '[':
                s0 = '['
                v = v[1:]
            elif v[0] == '(':
                s0 = '('
                v = v[1:]
            else:
                s0 = ''
            if v[-1] == ']':
                s1 = ']'
                v = v[0:-1]
            elif v[-1] == ')':
                s1 = ')'
                v = v[0:-1]
            else:
                s1 = ''
            v0 = v
            v1 = v
            p = v.find(',')
            if p >= 0:
                v0 = v[0:p]
                v1 = v[p+1:]
            self.version_sets.append((s0, s1, MavenVersion(v0), MavenVersion(v1),))
        if len(self.version_sets) <= 0:
            self.version_sets.append(('(', ')', MavenVersion('0'), MavenVersion('99999',)))
    
    def is_vague(self) -> bool:
        # if self.explicit_value:
        #     return False
        if len(self.version_sets) != 1:
            return True
        if self.version_sets[0][0] == '(' or self.version_sets[0][1] == ')':
            return True
        return self.version_sets[0][2] != self.version_sets[0][3]
    
    def best_fit(self, meta: MavenMetaFile) -> Optional[MavenVersion]:
        assert isinstance(meta, MavenMetaFile)
        debug("  %> Finding best fit for `{0}`".format(self.version))
        
        best = None
        for vv in [meta.versions, meta.releases]:
            for source in vv:
                trace("  %%> Comparing against {0}".format(repr(source)))
                for vs in self.version_sets:
                    c0 = vs[2].compare(source)
                    c1 = vs[3].compare(source)
                    # Equate '[' and '' as the same.
                    if (vs[0] == '(' and c0 <= 0) or c0 < 0:
                        trace("  %%> - not a match (too old)")
                        continue
                    if (vs[1] == ')' and c1 >= 0) or c1 > 0:
                        trace("  %%> - not a match (too recent)")
                        continue
                    if best is None or best.compare(source) >= 0:
                        trace("  %%> - new best")
                        best = source
                    else:
                        trace("  %%> - existing best ({0}) is better".format(repr(best)))
        debug("  %> Found best fit {0} for {1}".format(repr(best), self.version))
        if best is None:
            debug("  %> No best fit with meta {0}".format([meta.versions, meta.releases]))
        return best
    
    def __str__(self) -> str:
        return "[declared: {0} -> {1}]".format(self.version, repr(self.version_sets))


# ---------------------------------------------------------------------------
# XML Handling Stuff

def parse_xml(filename: str, _tempdir: Optional[str] = None) -> xml.dom.minidom.Document:
    # The maven XML files are sometimes garbage and need some fixing.
    
    with open(filename, 'r') as f:
        contents = f.read()
    
    # We could fix this up by updating the parser to support all
    # kinds of special things, but instead we'll just directly fix the
    # XML.
    
    contents = contents.replace(
        # plexus 1.0.3 fix...
        '&oslash;', '-'
    ).replace(
        # javax/portlet/portlet-api fix...
        '&nbsp;', ' '
    ).replace(
        # com/amazonaws/aws-lambda-java-events contains unbound prefix xsi
        '<project xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/maven-v4_0_0.xsd">',
        '<project>'
    )
    
    try:
        return xml.dom.minidom.parseString(contents)
    except BaseException as err:
        warn("Error reading XML file " + filename)
        warn(str(err))
        warn("You may need to alter the `parse_xml` function to handle the invalid XML file.")
        raise


def xml_gettext(el: xml.dom.minidom.Element) -> str:
    r = []
    for n in el.childNodes:
        if n.nodeType == n.TEXT_NODE:
            r.append(n.data)
    return ''.join(r)


def xml_getnode_text(el: xml.dom.minidom.Element, tag_name: str) -> str:
    r = []
    for c in el.childNodes:
        if c.nodeType == c.ELEMENT_NODE and c.tagName == tag_name:
            r.append(xml_gettext(c))
    return ''.join(r)


def xml_getnodes(el: xml.dom.minidom.Element, tag_name: str) -> List[xml.dom.minidom.Element]:
    # Special case for root document
    el_list = [el]
    if el.nodeType != el.ELEMENT_NODE:
        el_list = []
        for c in el.childNodes:
            if c.nodeType == c.ELEMENT_NODE:
                el_list.append(c)

    r = []
    for p in el_list:
        for c in p.childNodes:
            if c.nodeType == c.ELEMENT_NODE and c.tagName == tag_name:
                r.append(c)
    return r


# ---------------------------------------------------------------------------
# Log Functions
def trace(msg: str) -> None:
    if CONFIG.can_log(LOG_TRACE):
        print("{0}TRACE: {1}".format(PROGRESS_EOL, msg), end=EOL)


def debug(msg: str) -> None:
    if CONFIG.can_log(LOG_DEBUG):
        print("{0}DEBUG: {1}".format(PROGRESS_EOL, msg), end=EOL)


def info(msg: str) -> None:
    if CONFIG.can_log(LOG_INFO):
        print(PROGRESS_EOL + str(msg), end=EOL)


def warn(msg: str) -> None:
    if CONFIG.can_log(LOG_WARN):
        print(PROGRESS_EOL + str(msg), end=EOL)


def progress(msg: str) -> None:
    if CONFIG.show_progress:
        outp = "      {0} {1}".format(CONFIG.progress_indicators[PROGRESS_INDEX[0]], msg)
        if COLUMN_COUNT > 0:
            outp = outp[:COLUMN_COUNT]
        print(outp, end=PROGRESS_EOL)
        PROGRESS_INDEX[0] = (PROGRESS_INDEX[0] + 1) % len(CONFIG.progress_indicators)
    else:
        debug(msg)


def tmpdir(outputdir: str) -> str:
    tmp = os.path.join(outputdir, '.tmp')
    if not os.path.isdir(tmp):
        warn("Creating temporary directory to store downloaded files at {0}".format(tmp))
        os.makedirs(tmp)
    return tmp


def is_valid_filename(filename: str) -> bool:
    # Some artifacts publish an md5 checksum of the md5 checksum, and so on,
    # which is clearly wrong.  Do not count these files as published artifacts.
    return not (
        filename.endswith(".md5.md5") or
        filename.endswith(".md5.sha1") or
        filename.endswith(".sha1.md5") or
        filename.endswith(".sha1.sha1")
    )


def check_license_name(license_name: str, against: str) -> bool:
    n = license_name.lower()
    p = re.sub(r'\s+', n, ' ')
    while n != p:
        n = p
        p = re.sub(r'\s+', p, ' ')
    return n.find(against.lower()) >= 0


def check_license_url(license_url: str, against: str) -> bool:
    return license_url.lower() == against.lower()


# ---------------------------------------------------------------------------
# General file utilities

def delete_file(filename: str) -> None:
    if os.path.isfile(filename):
        try:
            os.unlink(filename)
        except PermissionError:
            # Ignore.  Windows threading can encounter this issue.
            debug("Skipping permission error when deleting {0}".format(filename))
        except FileNotFoundError:
            # Ignore.  This can happen in some interesting situations on Windows.
            debug("Couldn't delete file because it doesn't exist: {0}".format(filename))


# ---------------------------------------------------------------------------
# Main Program
def main() -> None:
    parser = argparse.ArgumentParser(description="""Tool to download dependencies
from a remote Maven Repo for checking usage, before adding into the local maven
repo.  All the files in the remote repo for the artifact will be pulled down.""")
    parser.add_argument(
        '--version', dest='show_version', action='store_true', default=False,
        help="Show the program version and exit."
    )
    parser.add_argument(
        '-d', '--dir', dest='output', default=None,
        help="directory to store the downloaded files (defaults to the current directory)"
    )
    parser.add_argument(
        '-r', '--resolve', dest='recurse', action='store_true', default=None,
        help="resolve the POM files and their dependencies, recursively"
    )
    parser.add_argument(
        '-O', '--overwrite', dest='overwrite', action='store_true', default=None,
        help="overwrite any already existing file with the same name"
    )
    parser.add_argument(
        '-v', '--verbosity', dest='verbosity', action='count',
        help="increase output verbosity"
    )
    parser.add_argument(
        '-p', '--progress', dest='progress', action='store_true', default=None,
        help="Show progress indicator"
    )
    parser.add_argument(
        '-P', '--parent', dest='parent', action='store_true', default=None,
        help="Download dependency management children (declared in parent and bom files)"
    )
    parser.add_argument(
        '-e', '--error-file', dest='error_file', default=None,
        help="file to add the discovered problems to."
    )
    parser.add_argument(
        '-x', '--no-local', dest='no_local', action='store_false', default=None,
        help="do not search local URLs for the dependency."
    )
    parser.add_argument(
        '-t', '--no-remote-download', dest='do_remote_download', action='store_false', default=None,
        help="do not download files from the remote repo."
    )
    parser.add_argument(
        '--no-pgp', dest='no_pgp', action='store_true', default=None,
        help="do not perform PGP signature checking."
    )
    parser.add_argument(
        '--require-valid-license', dest='require_valid_license', action='store_true', default=None,
        help="Require that for all downloaded artifacts that define a license, it must be whitelisted."
    )
    parser.add_argument(
        '--require-license', dest='require_license', action='store_true', default=None,
        help="Require that all downloaded artifacts must define a license name or URL."
    )
    parser.add_argument(
        '-c', '--config', dest='config_file', default=None,
        help="configuration file to load"
    )
    parser.add_argument(
        'artifacts', metavar='artifact', nargs='+',
        help="artifact names to download.  These are either Maven-style URLs or gradle compact "
             "artifact notation (group:artifact:version)"
    )

    parsed = parser.parse_args()
    if parsed.show_version:
        print("v" + VERSION)
        sys.exit(0)

    if parsed.config_file:
        CONFIG.load(str(parsed.config_file))
    CONFIG.load(os.path.join(os.path.curdir, DEFAULT_CONFIGURATION_FILE_NAME))
    CONFIG.load(os.path.join(os.path.expanduser("~"), DEFAULT_CONFIGURATION_FILE_NAME))

    if parsed.output is not None:
        CONFIG.outdir = parsed.output
    if parsed.recurse is not None:
        CONFIG.recursive = parsed.recurse
    if parsed.overwrite is not None:
        CONFIG.overwrite = parsed.overwrite
    if parsed.progress is not None:
        CONFIG.show_progress = parsed.progress
    if parsed.parent is not None:
        CONFIG.include_dep_management = parsed.parent
    if parsed.no_local is not None:
        CONFIG.check_in_local = parsed.no_local
    if parsed.do_remote_download is not None:
        CONFIG.do_remote_download = parsed.do_remote_download
    if parsed.error_file is not None:
        CONFIG.problem_file = parsed.error_file
    if parsed.no_pgp is not None:
        CONFIG.no_pgp = parsed.no_pgp
    if parsed.require_valid_license is not None:
        CONFIG.allow_unacceptable_licenses = not parsed.require_valid_license
    if parsed.require_license is not None:
        CONFIG.allow_no_license = not parsed.require_license

    if parsed.verbosity == 1:
        CONFIG.log_level = LOG_INFO
    elif parsed.verbosity == 2:
        CONFIG.log_level = LOG_DEBUG
    elif parsed.verbosity is not None and parsed.verbosity >= 3:
        CONFIG.log_level = LOG_TRACE

    if not CONFIG.no_pgp:
        setup_gpg(CONFIG.outdir)
    
    for arg in parsed.artifacts:
        download_artifact(CONFIG.outdir, arg)


def exit_program(_code: int) -> None:
    if len(PROBLEMS) > 0:
        print(EOL + "Discovered problems:")
        print("    " + ("\n    ".join([str(p) for p in PROBLEMS])))
        if CONFIG.problem_file is not None:
            with open(CONFIG.problem_file, 'a') as f:
                if CONFIG.problem_file.endswith('.json'):
                    json.dump([p.json() for p in PROBLEMS], f)
                else:
                    f.write("\n".join([str(p) for p in PROBLEMS]) + "\n")
        for p in PROBLEMS:
            p.clean_violations()

    # sys.exit(_code)


if __name__ == '__main__':
    try:
        main()
        exit_program(0)
    except BaseException:
        exit_program(1)
        raise
