import sys
import os
import glob
import unittest

from qemu import qemu_bin_arch, QEMUMachine


def get_built_qemu_binaries(src_root='/home/cleber/disposable/src/qemu'):
    if src_root is None:
        src_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    binaries = glob.glob(os.path.join(src_root, '*-softmmu/qemu-system-*'))
    if 'win' in sys.platform:
        bin_filter = lambda x: x.endswith(".exe")
    else:
        bin_filter = lambda x: not x.endswith(".exe")
    return [_ for _ in binaries if bin_filter(_)]


class QEMU(unittest.TestCase):

    @unittest.skipUnless(get_built_qemu_binaries(),
                         "Could not find any QEMU binaries built to use on "
                         "arch check")
    def test_qemu_bin_arch(self):
        """
        Checks that the qemu_bin_arch returns the expected architecture name

        To avoid duplication of information, we assume the archicture matches
        the last part of the binary name.
        """
        for binary in get_built_qemu_binaries():
            self.assertEqual(qemu_bin_arch(binary),
                             binary.split('-')[-1].split(".exe")[0])

    # @unittest.skipUnless('/home/cleber/disposable/src/qemu/s390x-softmmu/qemu-system-s390x'
    #                      in get_built_qemu_binaries(), 'no s390x')
    @unittest.skipUnless(get_built_qemu_binaries(),
                         "Could not find any QEMU binaries built to use on "
                         "arch check")
    def test_auto_console(self):
        import logging
        logging.basicConfig(level=logging.DEBUG)
        # FIXME: targets that don't accept a serial console or have some other issues
        #exception_list = ['qemu-system-xtensaeb', 'qemu-system-ppc64', 'qemu-system-aarch64', ]
        for binary in get_built_qemu_binaries():
            #if os.path.basename(binary) in exception_list:
            #    continue
            qemu_machine = QEMUMachine(binary, automatic_devices=True)
            qemu_machine.launch()
            #self.assertIsNotNone(qemu_machine._console_address)
            qemu_machine.shutdown()

if __name__ == '__main__':
    unittest.main()
