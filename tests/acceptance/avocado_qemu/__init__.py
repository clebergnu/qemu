import os
import sys

import avocado

SRC_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
SRC_ROOT_DIR = os.path.abspath(os.path.dirname(SRC_ROOT_DIR))
sys.path.append(os.path.join(SRC_ROOT_DIR, 'scripts'))

from qemu import QEMUMachine


def qemu_bin_by_arch(arch):
    """
    Returns the path of a QEMU binary, according to the given arch

    TODO: should also support a different build directory
    """
    qemu_binary = os.path.join(SRC_ROOT_DIR,
                               "%s-softmmu" % arch, "qemu-system-%s" % arch)
    if os.path.exists(qemu_binary):
        return qemu_binary


class Test(avocado.Test):
    def setUp(self):
        self.vm = None
        self.qemu_bin = None
        self.arch = self.params.get('arch', default=os.uname()[4])
        self.qemu_bin = self.params.get('qemu_bin',
                                        default=qemu_bin_by_arch(self.arch))
        if self.qemu_bin is None:
            self.cancel("No QEMU binary defined or found in the source tree")
        self.vm = QEMUMachine(self.qemu_bin)

    def tearDown(self):
        if self.vm is not None:
            self.vm.shutdown()
