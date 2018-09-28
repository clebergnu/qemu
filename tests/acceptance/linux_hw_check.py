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


class LinuxHWCheck(Test):
    """
    Boots a Linux system, checking for a successful initialization

    :avocado: enable
    """

    timeout = 600

    def xxx_test_boot(self):
        self.set_vm_image()
        self.set_vm_cloudinit()
        self.vm.launch()
        self.wait_for_vm_boot()

    def test_hw_resources(self):
        self.set_vm_image()
        self.set_vm_cloudinit()
        ssh_port = network.find_free_port(start_port=self.vm_hw['phone_home_port']+1)
        self.vm.add_session_network(ssh_port)
        self.vm.launch()
        self.wait_for_vm_boot()

        priv_key = os.path.join(self.vm_hw['key_path'], 'id_rsa')
        with ssh.Session(('127.0.0.1', ssh_port),
                         ('root', priv_key)) as session:
            # cpu
            proc_count_cmd = 'egrep -c "^processor\s\:" /proc/cpuinfo'
            self.assertEqual(int(self.vm_hw['smp']),
                             int(session.cmd(proc_count_cmd).stdout_text.strip()))

            # memory
            match = re.match(r"^MemTotal:\s+(\d+)\skB",
                             session.cmd('cat /proc/meminfo').stdout_text.strip())
            self.assertIsNotNone(match)
            exact_mem_kb = int(self.vm_hw['memory']) * 1024
            guest_mem_kb = int(match.group(1))
            self.assertGreaterEqual(guest_mem_kb, exact_mem_kb * 0.9)
            self.assertLessEqual(guest_mem_kb, exact_mem_kb)
