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

from avocado.utils import cloudinit
from avocado.utils import vmimage
from avocado.utils import network
from avocado.utils import genio

SRC_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
SRC_ROOT_DIR = os.path.abspath(os.path.dirname(SRC_ROOT_DIR))
sys.path.append(os.path.join(SRC_ROOT_DIR, 'scripts'))

from qemu import QEMUMachine

def is_readable_executable_file(path):
    return os.path.isfile(path) and os.access(path, os.R_OK | os.X_OK)


def pick_default_qemu_bin(arch=None):
    """
    Picks the path of a QEMU binary, starting either in the current working
    directory or in the source tree root directory.

    :param arch: the arch to use when looking for a QEMU binary (the target
                 will match the arch given).  If None (the default) arch
                 will be the current host system arch (as given by
                 :func:`os.uname`).
    :type arch: str
    :returns: the path to the default QEMU binary or None if one could not
              be found
    :rtype: str or None
    """
    if arch is None:
        arch = os.uname()[4]
    qemu_bin_relative_path = os.path.join("%s-softmmu" % arch,
                                          "qemu-system-%s" % arch)
    if is_readable_executable_file(qemu_bin_relative_path):
        return qemu_bin_relative_path

    qemu_bin_from_src_dir_path = os.path.join(SRC_ROOT_DIR,
                                              qemu_bin_relative_path)
    if is_readable_executable_file(qemu_bin_from_src_dir_path):
        return qemu_bin_from_src_dir_path


class Test(avocado.Test):
    def setUp(self):
        self.vm = None
        self.arch = self.params.get('arch', default=os.uname()[4])
        self.qemu_bin = self.params.get('qemu_bin',
                                        default=pick_default_qemu_bin(self.arch))
        if self.qemu_bin is None:
            self.cancel("No QEMU binary defined or found in the source tree")
        self.vm = QEMUMachine(self.qemu_bin)
        self._set_vm_hardware()

    def _set_vm_hardware(self):
        self.vm_hw = {}

        self.vm_hw['machine'] = self.params.get('machine', default='pc')
        self.vm.set_machine(self.vm_hw['machine'])

        self.vm_hw['accel'] = self.params.get('accel', default='kvm')
        self.vm.add_args('-accel', self.vm_hw['accel'])

        self.vm_hw['smp'] = self.params.get('smp', default='8')
        self.vm.add_args('-smp', self.vm_hw['smp'])

        self.vm_hw['memory'] = self.params.get('memory', default='4096')
        self.vm.add_args('-m', self.vm_hw['memory'])

        self.vm_hw['arch'] = self.params.get('arch', default=os.uname()[4])

    def set_vm_image(self):
        distro = self.params.get('distro', default='fedora')
        version = self.params.get('version', default='28')
        boot = vmimage.get(distro, arch=self.vm_hw['arch'], version=version,
                           cache_dir=self.cache_dirs[0],
                           snapshot_dir=self.workdir)
        self.vm.add_args('-drive', 'file=%s' % boot.path)

    def set_vm_cloudinit(self):
        # not really hardware configuration things...
        self.vm_hw['phone_home_port'] = network.find_free_port()
        self.vm_hw['key_path'] = os.path.join(os.path.dirname(
            os.path.dirname(os.path.dirname(__file__))), 'keys')
        self.vm_hw['pub_key'] = genio.read_file(os.path.join(self.vm_hw['key_path'],
                                                             'id_rsa.pub'))
        cloudinit_iso = os.path.join(self.workdir, 'cloudinit.iso')
        cloudinit.iso(cloudinit_iso, self.name,
                      username='root', password='root',
                      # QEMU's hard coded usermode router address
                      phone_home_host='10.0.2.2',
                      phone_home_port=self.vm_hw['phone_home_port'],
                      authorized_key=self.vm_hw['pub_key'])
        self.vm.add_args('-drive', 'file=%s' % cloudinit_iso)

    def wait_for_vm_boot(self):
        return cloudinit.wait_for_phone_home(
            ('0.0.0.0', self.vm_hw['phone_home_port']),
            self.name)

    def tearDown(self):
        if self.vm is not None:
            self.vm.shutdown()
