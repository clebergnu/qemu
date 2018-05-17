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


    TEST_ARCH_MACHINE_CONSOLES = {
        'alpha': ['clipper'],
        'mips': ['malta'],
        'x86_64': ['isapc',
                   'pc', 'pc-0.10', 'pc-0.11', 'pc-0.12', 'pc-0.13',
                   'pc-0.14', 'pc-0.15', 'pc-1.0', 'pc-1.1', 'pc-1.2',
                   'pc-1.3',
                   'pc-i440fx-1.4', 'pc-i440fx-1.5', 'pc-i440fx-1.6',
                   'pc-i440fx-1.7', 'pc-i440fx-2.0', 'pc-i440fx-2.1',
                   'pc-i440fx-2.10', 'pc-i440fx-2.11', 'pc-i440fx-2.2',
                   'pc-i440fx-2.3', 'pc-i440fx-2.4', 'pc-i440fx-2.5',
                   'pc-i440fx-2.6', 'pc-i440fx-2.7', 'pc-i440fx-2.8',
                   'pc-i440fx-2.9', 'pc-q35-2.10', 'pc-q35-2.11',
                   'q35', 'pc-q35-2.4', 'pc-q35-2.5', 'pc-q35-2.6',
                   'pc-q35-2.7', 'pc-q35-2.8', 'pc-q35-2.9'],
        'ppc64': ['40p', 'powernv', 'prep', 'pseries', 'pseries-2.1',
                  'pseries-2.2', 'pseries-2.3', 'pseries-2.4', 'pseries-2.5',
                  'pseries-2.6', 'pseries-2.7', 'pseries-2.8', 'pseries-2.9',
                  'pseries-2.10', 'pseries-2.11', 'pseries-2.12'],
        's390x': ['s390-ccw-virtio', 's390-ccw-virtio-2.4',
                  's390-ccw-virtio-2.5', 's390-ccw-virtio-2.6',
                  's390-ccw-virtio-2.7', 's390-ccw-virtio-2.8',
                  's390-ccw-virtio-2.9', 's390-ccw-virtio-2.10',
                  's390-ccw-virtio-2.11', 's390-ccw-virtio-2.12']
    }


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

    def test_set_console(self):
        for (arch, machines) in QEMU.TEST_ARCH_MACHINE_CONSOLES.items():
            for machine in machines:
                qemu_machine = qemu.QEMUMachine('/fake/path/to/binary',
                                                arch=arch)
                qemu_machine.set_machine(machine)
                qemu_machine.set_console()

    def test_set_console_no_machine(self):
        qemu_machine = qemu.QEMUMachine('/fake/path/to/binary', arch='fake')
        self.assertRaises(qemu.QEMUMachineAddDeviceError,
                          qemu_machine.set_console)

    def test_set_console_no_machine_match(self):
        qemu_machine = qemu.QEMUMachine('/fake/path/to/binary', arch='x86_64')
        qemu_machine.set_machine('unknown-machine-model')
        self.assertRaises(qemu.QEMUMachineAddDeviceError,
                          qemu_machine.set_console)

    @unittest.skipUnless(get_built_qemu_binaries(),
                         "Could not find any QEMU binaries built to use on "
                         "console check")
    def test_set_console_launch(self):
        for binary in get_built_qemu_binaries():
            probed_arch = qemu.qemu_bin_probe_arch(binary)
            for machine in QEMU.TEST_ARCH_MACHINE_CONSOLES.get(probed_arch, []):
                qemu_machine = qemu.QEMUMachine(binary, arch=probed_arch)

                # the following workarounds are target specific required for
                # this test.  users are of QEMUMachine are expected to deal with
                # target specific requirements just the same in their own code
                cap_htm_off = ('pseries-2.7', 'pseries-2.8', 'pseries-2.9',
                               'pseries-2.10', 'pseries-2.11', 'pseries-2.12')
                if probed_arch == 'ppc64' and machine in cap_htm_off:
                    qemu_machine._machine = machine
                    qemu_machine._args.extend(['-machine',
                                               '%s,cap-htm=off' % machine])
                elif probed_arch == 's390x':
                    qemu_machine.set_machine(machine)
                    qemu_machine._args.append('-nodefaults')
                elif probed_arch == 'mips':
                    # TODO: use a portable file, even if it's a fake one
                    qemu_machine.set_machine(machine)
                    qemu_machine._args.extend(['-bios', '/dev/null'])
                else:
                    qemu_machine.set_machine(machine)

                qemu_machine.set_console()
                qemu_machine.launch()
                qemu_machine.shutdown()


if __name__ == '__main__':
    unittest.main()
