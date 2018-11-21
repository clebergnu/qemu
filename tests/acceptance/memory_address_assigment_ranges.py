# Test for the memory address assigment rewrite using ranges
#
# Copyright (c) 2018 Red Hat, Inc.
#
# Author:
#  Cleber Rosa <crosa@redhat.com>
#
# This work is licensed under the terms of the GNU GPL, version 2 or
# later.  See the COPYING file in the top-level directory.

from avocado import Test
from avocado_qemu import pick_default_qemu_bin
from avocado.utils import process


class Memory(Test):
    """
    :avocado: tags=quick,memory
    """
    def test_cant_add_memory_device(self):
        qemu_bin = self.params.get('qemu_bin',
                                   default=pick_default_qemu_bin())
        args = ('-nodefaults -nographic -S -m 4G,slots=20,maxmem=40G '
                '-object memory-backend-file,id=mem1,share,mem-path=/dev/zero,size=2G '
                '-device pc-dimm,memdev=mem1,id=dimm1,addr=-0x40000000')
        cmd = '%s %s' % (qemu_bin, args)
        res = process.run(cmd, ignore_status=True, timeout=1)
        self.assertEqual(res.exit_status, 1,
                         'QEMU command expected to error, but succeeded. '
                         'Command: %s' % cmd)
        self.assertIn("can't add memory device [0xffffffffc0000000:0x80000000], "
                      "range overflow",
                      res.stderr_text)
