from avocado_qemu import Test


class Version(Test):
    """
    :avocado: enable
    :avocado: tags=quick
    """
    def test_qmp_human_info_version(self):
        self.vm.launch()
        res = self.vm.qmp('human-monitor-command', command_line='info version')
        self.assertRegexpMatches(res['return'], r'^(\d+\.\d+\.\d)')
