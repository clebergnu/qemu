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

from avocado.utils import cloudinit
from avocado.utils import network
from avocado.utils import vmimage
from avocado.utils import remote
from avocado.utils import genio


class LinuxHWCheck(Test):
    """
    Boots a Linux system, checking for a successful initialization

    :avocado: enable
    """

    timeout = 600

    def test(self):
        self.vm.set_machine(self.params.get('machine', default='pc'))
        self.vm.add_args('-accel', self.params.get('accel', default='kvm'))
        smp = self.params.get('smp', default='8')
        self.vm.add_args('-smp', smp)
        mem = self.params.get('memory', default='4096')
        self.vm.add_args('-m', mem)

        arch = self.params.get('arch', default=os.uname()[4])
        distro = self.params.get('distro', default='fedora')
        version = self.params.get('version', default='28')
        boot = vmimage.get(distro, arch=arch, version=version,
                           cache_dir=self.cache_dirs[0],
                           snapshot_dir=self.workdir)
        self.vm.add_args('-drive', 'file=%s' % boot.path)

        key_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'keys')
        pub_key = genio.read_file(os.path.join(key_path, 'id_rsa.pub'))

        cloudinit_iso = os.path.join(self.workdir, 'cloudinit.iso')
        phone_home_port = network.find_free_port()
        cloudinit.iso(cloudinit_iso, self.name,
                      username='root', password='root',
                      # QEMU's hard coded usermode router address
                      phone_home_host='10.0.2.2',
                      phone_home_port=phone_home_port,
                      authorized_key=pub_key)
        self.vm.add_args('-drive', 'file=%s' % cloudinit_iso)

        ssh_port = network.find_free_port(start_port=phone_home_port+1)
        self.vm.add_args('-netdev', 'user,id=user,hostfwd=tcp:127.0.0.1:%d-:22' % ssh_port)
        self.vm.add_args('-device', 'e1000,netdev=user')
        self.vm.add_args('-vnc', ':0')

        self.vm.launch()
        cloudinit.wait_for_phone_home(('0.0.0.0', phone_home_port), self.name)
        with remote.SSHSession(remote.IPAddress('127.0.0.1', ssh_port),
                               ('root', os.path.join(key_path, 'id_rsa'))) as session:
            # cpu
            proc_count_cmd = 'egrep -c "^processor\s\:" /proc/cpuinfo'
            self.assertEqual(int(smp),
                             int(session.cmd(proc_count_cmd).stdout_text.strip()))
            # memory
            match = re.match(r"^MemTotal:\s+(\d+)\skB",
                             session.cmd('cat /proc/meminfo').stdout_text.strip())
            self.assertIsNotNone(match)
            exact_mem_kb = int(mem) * 1024
            guest_mem_kb = int(match.group(1))
            self.assertGreaterEqual(guest_mem_kb, exact_mem_kb * 0.9)
            self.assertLessEqual(guest_mem_kb, exact_mem_kb)
