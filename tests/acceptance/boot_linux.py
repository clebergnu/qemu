# Functional test that boots a complete Linux system via a cloud image
#
# Copyright (c) 2018 Red Hat, Inc.
#
# Author:
#  Cleber Rosa <crosa@redhat.com>
#
# This work is licensed under the terms of the GNU GPL, version 2 or
# later.  See the COPYING file in the top-level directory.

import os
import re

from avocado_qemu import Test

from avocado.utils import network
from avocado.utils import ssh


class Boot(Test):
    """
    Boots a Linux system, checking for a successful initialization

    :avocado: enable
    """

    timeout = 600

    def test(self):
        self.set_vm_image()
        self.set_vm_cloudinit()
        self.vm.add_args('-vnc', ':0')
        self.vm.launch()
        self.wait_for_vm_boot()
