import os
import sys

import avocado
from avocado.utils import path
from avocado.utils import process

sys.path.append(os.path.join(os.path.dirname(__file__),
                             '..', '..', '..', 'scripts'))
from qemu import QEMUMachine


def qemu_bin_by_arch(arch):
    git_root = process.system_output('git rev-parse --show-toplevel',
                                     ignore_status=True,
                                     verbose=False)
    qemu_binary = os.path.join(git_root,
                               "%s-softmmu" % arch,
                               "qemu-system-%s" % arch)
    if not os.path.exists(qemu_binary):
        qemu_binary = utils_path.find_command('qemu-system-%s' % arch)
    return qemu_binary


class Test(avocado.Test):
    def setUp(self):
        self.arch = self.params.get('arch', default='x86_64')
        self.qemu_bin = self.params.get('qemu_bin',
                                        default=qemu_bin_by_arch(self.arch))
        self.vm = QEMUMachine(self.qemu_bin, arch=self.arch)

    def tearDown(self):
        self.vm.shutdown()
