import sys
import os
import glob
import unittest

try:
    from unittest import mock
    MOCK_AVAILABLE = True
except ImportError:
    try:
        import mock
        MOCK_AVAILABLE = True
    except ImportError:
        MOCK_AVAILABLE = False


import qemu


def get_built_qemu_binaries(src_root=None):
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
    def test_qemu_bin_probe_arch(self):
        """
        Checks that the qemu_bin_arch returns the expected architecture name

        To avoid duplication of information, we assume the archicture matches
        the last part of the binary name.
        """
        for binary in get_built_qemu_binaries():
            self.assertEqual(qemu.qemu_bin_probe_arch(binary),
                             binary.split('-')[-1].split(".exe")[0])

    @unittest.skipUnless(MOCK_AVAILABLE, "mock library not available")
    def test_qemu_bin_probe_arch_non_deterministic(self):
        """
        Checks that an exception is raised when the response from the
        QEMU binary is not deterministic.
        """
        with mock.patch('qemu.qmp_execute', return_value=None):
            self.assertRaises(qemu.QEMUMachineProbeError,
                              qemu.qemu_bin_probe_arch, '/fake/path/to/binary')

    @unittest.skipUnless(MOCK_AVAILABLE, "mock library not available")
    def test_qemu_machine_probe_arch(self):
        """
        Checks that a successfull standalone probe will set the machine arch
        """
        machine = qemu.QEMUMachine("/fake/path/to/binary", arch=None)
        self.assertIsNone(machine._arch)
        with mock.patch('qemu.qemu_bin_probe_arch', return_value='xyz_arch'):
            machine.probe_arch()
        self.assertEqual(machine._arch, 'xyz_arch')


if __name__ == '__main__':
    unittest.main()
