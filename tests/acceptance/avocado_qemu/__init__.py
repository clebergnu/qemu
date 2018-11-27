# Test class and utilities for functional tests
#
# Copyright (c) 2018 Red Hat, Inc.
#
# Author:
#  Cleber Rosa <crosa@redhat.com>
#
# This work is licensed under the terms of the GNU GPL, version 2 or
# later.  See the COPYING file in the top-level directory.

import os
import sys

import avocado

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
TOP_DIR = os.path.dirname(os.path.dirname(os.path.dirname(THIS_DIR)))
PYTHON_MODULE_PATH = os.path.join(TOP_DIR, 'python')
sys.path.append(PYTHON_MODULE_PATH)

from qemu import QEMUMachine

def is_readable_executable_file(path):
    return os.path.isfile(path) and os.access(path, os.R_OK | os.X_OK)


def pick_default_qemu_bin():
    """
    Picks the path of a QEMU binary, starting either in the current working
    directory or in the source tree root directory.
    """
    arch = os.uname()[4]
    qemu_bin_relative_path = os.path.join("%s-softmmu" % arch,
                                          "qemu-system-%s" % arch)
    if is_readable_executable_file(qemu_bin_relative_path):
        return qemu_bin_relative_path

    qemu_bin_from_src_dir_path = os.path.join(TOP_DIR,
                                              qemu_bin_relative_path)
    if is_readable_executable_file(qemu_bin_from_src_dir_path):
        return qemu_bin_from_src_dir_path


class Test(avocado.Test):
    def setUp(self):
        self.vm = None
        self.qemu_bin = self.params.get('qemu_bin',
                                        default=pick_default_qemu_bin())
        if self.qemu_bin is None:
            self.cancel("No QEMU binary defined or found in the source tree")
        self.vm = QEMUMachine(self.qemu_bin)

    def tearDown(self):
        if self.vm is not None:
            self.vm.shutdown()
