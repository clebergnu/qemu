import socket
import logging

from avocado_qemu import Test


def get_console_file_obj(qemu_machine):
    console_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    console_socket.connect(qemu_machine.console_address)
    return console_socket.makefile()


class BootConsole(Test):
    """
    :avocado: enable
    """

    timeout = 60

    def setUp(self):
        super(BootConsole, self).setUp()
        kernel_url = ('https://mirrors.kernel.org/fedora/releases/28/'
                      'Everything/%s/os/images/pxeboot/vmlinuz' % self.arch)
        kernel_url = self.params.get('kernel_url', default=kernel_url)
        self.kernel_path = self.fetch_asset(kernel_url)

    def test(self):
        self.vm.probe_arch()
        self.vm.set_machine('pc')
        self.vm.set_console()
        kernel_command_line = 'console=ttyS0'
        self.vm._args.extend(['-kernel', self.kernel_path,
                              '-append', kernel_command_line])
        self.vm.launch()
        console = get_console_file_obj(self.vm)
        console_logger = logging.getLogger('console')
        while True:
            msg = console.readline()
            console_logger.debug(msg.strip())
            if 'Kernel command line: %s' % kernel_command_line in msg:
                break
            if 'Kernel panic - not syncing' in msg:
                self.fail("Kernel panic reached")
