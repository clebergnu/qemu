# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
# See LICENSE for more details.
#
# Copyright (C) 2017 Red Hat Inc
#
# Authors:
#  Amador Pahim <apahim@redhat.com>
#
# Based on code from:
#   https://github.com/avocado-framework/avocado-virt


"""
Avocado Qemu Test module to extend the Avocado Test module providing
extra features intended for Qemu testing.
"""


import logging
import os
import re
import sys
import tempfile
import time
import uuid

import aexpect

from avocado import Test
from avocado.utils.data_structures import Borg
from avocado.utils import network
from avocado.utils import process
from avocado.utils import path as utils_path
from avocado.utils import wait

QEMU_ROOT = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(__file__)))))
sys.path.append(os.path.join(QEMU_ROOT, 'scripts'))
import qemu


class QEMULoginTimeoutError(Exception):
    """
    If timeout expires
    """


class QEMULoginAuthenticationError(Exception):
    """
    If authentication fails
    """


class QEMULoginProcessTerminatedError(Exception):
    """
    If the client terminates during login
    """


class QEMULoginError(Exception):
    """
    If some other error occurs
    """


class QEMUConsoleError(Exception):
    """
    If some error with the console access happens
    """


class QEMUMigrationError(Exception):
    """
    If some error with the migration happens
    """


class QEMUCloudinitError(Exception):
    """
    If some error with the migration happens
    """


def _get_qemu_bin(arch):
    git_root = process.system_output('git rev-parse --show-toplevel',
                                     ignore_status=True,
                                     verbose=False)
    qemu_binary = os.path.join(git_root,
                               "%s-softmmu" % arch,
                               "qemu-system-%s" % arch)
    if not os.path.exists(qemu_binary):
        qemu_binary = utils_path.find_command('qemu-system-%s' % arch)
    return qemu_binary


def _handle_prompts(session, username, password, prompt, timeout=60,
                    debug=False):
    """
    Connect to a remote host (guest) using SSH or Telnet or else.

    Wait for questions and provide answers.  If timeout expires while
    waiting for output from the child (e.g. a password prompt or
    a shell prompt) -- fail.

    :param session: An Expect or ShellSession instance to operate on
    :param username: The username to send in reply to a login prompt
    :param password: The password to send in reply to a password prompt
    :param prompt: The shell prompt that indicates a successful login
    :param timeout: The maximal time duration (in seconds) to wait for each
            step of the login procedure (i.e. the "Are you sure" prompt, the
            password prompt, the shell prompt, etc)
    :raise QEMULoginTimeoutError: If timeout expires
    :raise QEMULoginAuthenticationError: If authentication fails
    :raise QEMULoginProcessTerminatedError: If the client terminates during login
    :raise QEMULoginError: If some other error occurs
    :return: If connect succeed return the output text to script for further
             debug.
    """
    re_kernel_message = re.compile(r"^\[\s*\d+.\d+\] ")

    def get_last_nonempty_line(cont):
        """Return last non-empty non-kernel line"""
        nonempty_lines = [_ for _ in cont.splitlines()
                          if _.strip() and not re_kernel_message.match(_)]
        if nonempty_lines:
            return nonempty_lines[-1]
        else:
            return ""

    password_prompt_count = 0
    login_prompt_count = 0
    last_chance = False
    # Send enter to refresh output (in case session was attached after boot)
    session.sendline()
    output = ""
    while True:
        try:
            match, text = session.read_until_output_matches(
                [r"[Aa]re you sure", r"[Pp]assword:\s*",
                 # Prompt of rescue mode for Red Hat.
                 r"\(or (press|type) Control-D to continue\):\s*",
                 r"[Gg]ive.*[Ll]ogin:\s*",  # Prompt of rescue mode for SUSE.
                 r"(?<![Ll]ast )[Ll]ogin:\s*",  # Don't match "Last Login:"
                 r"[Cc]onnection.*closed", r"[Cc]onnection.*refused",
                 r"[Pp]lease wait", r"[Ww]arning", r"[Ee]nter.*username",
                 r"[Ee]nter.*password", r"[Cc]onnection timed out", prompt,
                 r"Escape character is.*"], get_last_nonempty_line,
                timeout=timeout, internal_timeout=0.5)
            output += text
            if match == 0:  # "Are you sure you want to continue connecting"
                if debug:
                    logging.debug("Got 'Are you sure...', sending 'yes'")
                session.sendline("yes")
                continue
            elif match in [1, 2, 3, 10]:  # "password:"
                if password_prompt_count == 0:
                    if debug:
                        logging.debug("Got password prompt, sending '%s'",
                                      password)
                    session.sendline(password)
                    password_prompt_count += 1
                    continue
                else:
                    raise QEMULoginAuthenticationError("Got password prompt "
                                                       "twice", text)
            elif match == 4 or match == 9:  # "login:"
                if login_prompt_count == 0 and password_prompt_count == 0:
                    if debug:
                        logging.debug("Got username prompt; sending '%s'",
                                      username)
                    session.sendline(username)
                    login_prompt_count += 1
                    continue
                else:
                    if login_prompt_count > 0:
                        msg = "Got username prompt twice"
                    else:
                        msg = "Got username prompt after password prompt"
                    raise QEMULoginAuthenticationError(msg, text)
            elif match == 5:  # "Connection closed"
                raise QEMULoginError("Client said 'connection closed'", text)
            elif match == 6:  # "Connection refused"
                raise QEMULoginError("Client said 'connection refused'", text)
            elif match == 11:  # Connection timeout
                raise QEMULoginError("Client said 'connection timeout'", text)
            elif match == 7:  # "Please wait"
                if debug:
                    logging.debug("Got 'Please wait'")
                timeout = 30
                continue
            elif match == 8:  # "Warning added RSA"
                if debug:
                    logging.debug("Got 'Warning added RSA to known host list")
                continue
            elif match == 12:  # prompt
                if debug:
                    logging.debug("Got shell prompt -- logged in")
                break
            elif match == 13:  # console prompt
                logging.debug("Got console prompt, send return to show login")
                session.sendline()
        except aexpect.ExpectTimeoutError as details:
            # sometimes, linux kernel print some message to console
            # the message maybe impact match login pattern, so send
            # a empty line to avoid unexpect login timeout
            if not last_chance:
                time.sleep(0.5)
                session.sendline()
                last_chance = True
                continue
            else:
                raise QEMULoginTimeoutError(details.output)
        except aexpect.ExpectProcessTerminatedError as details:
            raise QEMULoginProcessTerminatedError(details.status, details.output)

    return output


class _PortTracker(Borg):

    """
    Tracks ports used in the host machine.
    """

    def __init__(self):
        Borg.__init__(self)
        self.address = 'localhost'
        self.start_port = 5000
        if not hasattr(self, 'retained_ports'):
            self._reset_retained_ports()

    def __str__(self):
        return 'Ports tracked: %r' % self.retained_ports

    def _reset_retained_ports(self):
        self.retained_ports = []

    def register_port(self, port):
        if ((port not in self.retained_ports) and
                (network.is_port_free(port, self.address))):
            self.retained_ports.append(port)
        else:
            raise ValueError('Port %d in use' % port)
        return port

    def find_free_port(self, start_port=None):
        if start_port is None:
            start_port = self.start_port
        port = start_port
        while ((port in self.retained_ports) or
               (not network.is_port_free(port, self.address))):
            port += 1
        self.retained_ports.append(port)
        return port

    def release_port(self, port):
        if port in self.retained:
            self.retained.remove(port)


class _VM(qemu.QEMUMachine):
    '''A QEMU VM'''

    def __init__(self, qemu_bin=None, arch=None, qemu_dst_bin=None):
        if arch is None:
            arch = os.uname()[4]
        self.arch = arch
        self.ports = _PortTracker()
        self.name = "qemu-%s" % str(uuid.uuid4())[:8]
        if qemu_bin is None:
            qemu_bin = _get_qemu_bin(arch)
        if qemu_dst_bin is None:
            qemu_dst_bin = qemu_bin
        self.qemu_bin = qemu_bin
        self.qemu_dst_bin = qemu_dst_bin
        self.username = None
        self.password = None
        super(_VM, self).__init__(qemu_bin, name=self.name, arch=arch)
        logging.getLogger('QMP').setLevel(logging.INFO)

    def get_console(self, console_address=None, prompt=r"[\#\$] "):
        """
        :param address: Socket address, can be either a unix socket path
                        (string) or a tuple in the form (address, port)
                        for a TCP connection
        :param prompt: The regex to identify we reached the prompt.
        """

        if not all((self.username, self.password)):
            raise QEMUConsoleError('Username or password not set.')

        if not self.is_running():
            raise QEMUConsoleError('VM is not running.')

        if console_address is None:
            if self._console_address is None:
                raise QEMUConsoleError("Can't determine the console address "
                                       "to connect to.")
            else:
                console_address = self._console_address

        nc_cmd = 'nc'
        if isinstance(console_address, tuple):
            nc_cmd += ' %s %s' % (console_address[0], console_address[1])
        else:
            nc_cmd += ' -U %s' % console_address

        console = aexpect.ShellSession(nc_cmd)
        try:
            logging.info('Console: Waiting login prompt...')
            _handle_prompts(console, self.username, self.password, prompt)
            logging.info('Console: Ready!')
        except:
            console.close()
            raise

        return console

    def migrate(self, console_address=None, timeout=20):
        def migrate_complete():
            cmd = 'info migrate'
            res = self.qmp('human-monitor-command', command_line=cmd)
            if 'completed' in res['return']:
                logging.info("Migration successful")
                return True
            elif 'failed' in res['return']:
                raise QEMUMigrateError("Migration of %s failed" % self)
            return False

        port = self.ports.find_free_port()
        newvm = _VM(self.qemu_dst_bin, self._arch)
        newvm.args = self.args
        newvm.args.extend(['-incoming', 'tcp:0:%s' % port])
        newvm.username = self.username
        newvm.password = self.password

        newvm.launch(console_address)
        cmd = 'migrate -d tcp:0:%s' % port
        self.qmp('human-monitor-command', command_line=cmd)
        mig_result = wait.wait_for(migrate_complete, timeout=timeout,
                                   text='Waiting for migration to complete')

        if mig_result is None:
            raise QEMUMigrateError("Migration of %s did not complete after "
                                   "%s s" % (self.name, timeout))

        return newvm

    def add_image(self, path, username=None, password=None, snapshot=True,
                  extra=None):
        """
        Adds the '-drive' command line option and its parameters to
        the Qemu VM

        :param path: Image path (i.e. /var/lib/images/guestos.qcow2)
        :param username: The username to login into the Guest OS with
        :param password: The password to login into the Guest OS with
        :param snapshot: Whether the parameter snapshot=on will be used
        :param extra: Extra parameters to the -drive option
        """
        file_option = 'file=%s' % path
        for item in self.args:
            if file_option in item:
                logging.error('Image %s already present', path)
                return

        if extra is not None:
            file_option += ',%s' % extra

        if snapshot:
            file_option += ',snapshot=on'

        self.args.extend(['-drive', file_option])

        if username is not None:
            self.username = username

        if password is not None:
            self.password = password

    def add_machine(self, machine_type=None, machine_accel=None,
                    machine_kvm_type=None):
        """
        Adds the '-machine' command line option and its parameters
        to the Qemu VM

        :param machine_type: The machine type to be used (i.e. pc)
        :param machine_accel: The machine acceleration to be use (i.e. kvm)
        :param machine_kvm_type: If using kvm, the kvm type (i.e. PR)
        """
        if '-machine' in self.args:
            logging.error('Option -machine already present')
            return

        machine = []
        if machine_type is not None:
            machine.append(machine_type)
        if machine_accel is not None:
            machine.append("accel=%s" % machine_accel)
        if machine_kvm_type is not None:
            machine.append("kvm-type=%s" % machine_kvm_type)

        if not machine:
            logging.error('Option -machine needs argument')
            return

        self.args.extend(['-machine', ','.join(machine)])

    def cloudinit(self, hostname=None, password=None):
        """
        Creates a CDROM Iso Image with the required cloudinit files
        (meta-data and user-data) to make the initial Cloud Image
        configuration, attaching the CDROM to the VM.

        :param: hostname: The hostname to configure the image with
        :param password: The password to configure the default user with
        """
        try:
            geniso_bin = utils_path.find_command('genisoimage')
        except:
            raise QEMUCloudinitError('Command not found (genisoimage)')

        if hostname is None:
            hostname = self.name

        if password is None:
            password = self.password

        data_dir = tempfile.mkdtemp()

        metadata_path = os.path.join(data_dir, 'meta-data')
        metadata_content = ("instance-id: %s\n"
                            "local-hostname: %s\n" % (hostname, hostname))
        with open(metadata_path, 'w') as metadata_file:
            metadata_file.write(metadata_content)

        userdata_path = os.path.join(data_dir, 'user-data')
        userdata_content = ("#cloud-config\n"
                            "password: %s\n"
                            "ssh_pwauth: True\n"
                            "chpasswd: { expire: False }\n" % password)
        with open(userdata_path, 'w') as userdata_file:
            userdata_file.write(userdata_content)

        iso_path = os.path.join(data_dir, 'cdrom.iso')
        process.run("%s -output %s -volid cidata -joliet -rock %s %s" %
                    (geniso_bin, iso_path, metadata_path, userdata_path))

        self.args.extend(['-cdrom', iso_path])


class QemuTest(Test):

    def __init__(self, methodName=None, name=None, params=None,
                 base_logdir=None, job=None, runner_queue=None):
        super(QemuTest, self).__init__(methodName=methodName, name=name,
                                       params=params, base_logdir=base_logdir,
                                       job=job, runner_queue=runner_queue)
        self.vm = _VM(qemu_bin=self.params.get('qemu_bin'),
                      arch=self.params.get('arch'),
                      qemu_dst_bin=self.params.get('qemu_dst_bin'))

        machine_type = self.params.get('machine_type')
        machine_accel = self.params.get('machine_accel')
        machine_kvm_type = self.params.get('machine_kvm_type')
        if any((machine_type, machine_accel, machine_kvm_type)):
            self.vm.add_machine(machine_type, machine_accel, machine_kvm_type)