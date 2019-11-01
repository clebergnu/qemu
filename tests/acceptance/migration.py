# Migration test
#
# Copyright (c) 2019 Red Hat, Inc.
#
# Authors:
#  Cleber Rosa <crosa@redhat.com>
#  Caio Carrara <ccarrara@redhat.com>
#
# This work is licensed under the terms of the GNU GPL, version 2 or
# later.  See the COPYING file in the top-level directory.


from avocado_qemu import Test

from avocado.utils import network
from avocado.utils import wait


class Migration(Test):

    timeout = 10

    @staticmethod
    def migration_finished(vm):
        migrate_info = vm.command('query-migrate')
        return migrate_info.get('status') in ('completed', 'failed')

    def _get_free_port(self):
        port = network.find_free_port()
        if port is None:
            self.cancel('Failed to find a free port')
        return port

    def test_migration_with_tcp_localhost(self):
        source_vm = self.get_vm()
        dest_uri = 'tcp:localhost:%u' % self._get_free_port()
        dest_vm = self.get_vm('-incoming', dest_uri)
        dest_vm.launch()
        source_vm.launch()
        source_vm.qmp('migrate', uri=dest_uri)
        wait.wait_for(
            self.migration_finished,
            timeout=self.timeout,
            step=0.1,
            args=(source_vm,)
        )
        self.assertEqual(dest_vm.command('query-migrate')['status'], 'completed')
        self.assertEqual(source_vm.command('query-migrate')['status'], 'completed')
        self.assertEqual(dest_vm.command('query-status')['status'], 'running')
        self.assertEqual(source_vm.command('query-status')['status'], 'postmigrate')

    def test_migration_defer_multifd_on_localhost(self):
        source_vm = self.get_vm()
        dest_vm = self.get_vm('-incoming', 'defer')
        dest_vm.launch()
        dest_vm.qmp('migrate-set-capabilities',
                    capabilities=[{'state': True, 'capability': 'multifd'}])
        dest_uri = 'tcp:localhost:%u' % self._get_free_port()
        dest_vm.qmp('migrate-incoming', uri=dest_uri)
        source_vm.launch()
        source_vm.qmp('migrate', uri=dest_uri)
        self.assertEqual(source_vm.command('query-migrate')['status'], 'setup')

        wait.wait_for(
            self.migration_finished,
            timeout=self.timeout,
            step=0.1,
            args=(source_vm, )
        )

        self.assertEqual(source_vm.command('query-migrate')['status'], 'completed')
        self.assertEqual(dest_vm.command('query-status')['status'], 'inmigrate')
        # TODO: how does/should the dest_vm transition to 'status' == 'running' ?
        #self.assertEqual(dest_vm.command('query-status')['status'], 'running')
        self.assertEqual(source_vm.command('query-status')['status'], 'postmigrate')
