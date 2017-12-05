This directory is hosting functional tests written using Avocado Testing
Framework. To install Avocado, follow the instructions from this link::

    http://avocado-framework.readthedocs.io/en/latest/GetStartedGuide.html#installing-avocado

Tests here are written keeping the minimum amount of dependencies. To
run the tests, you need the Avocado core package (`python-avocado` on
Fedora, `avocado-framework` on pip). Extra dependencies should be
documented in this file.

In this directory, an ``avocado_qemu`` package is provided, containing
the ``test`` module, which inherits from ``avocado.Test`` and provides
a builtin and easy-to-use Qemu virtual machine. Here's a template that
can be used as reference to start writing your own tests::

    from avocado_qemu import test

    class MyTest(test.QemuTest):
        """
        :avocado: enable
        """

        def setUp(self):
            self.vm.args.extend(['-m', '512'])
            self.vm.launch()

        def test_01(self):
            res = self.vm.qmp('human-monitor-command',
                              command_line='info version')
            self.assertIn('v2.9.0', res['return'])

        def tearDown(self):
            self.vm.shutdown()

To execute your test, run::

    avocado run test_my_test.py

To execute all tests, run::

    avocado run .

If you don't specify the Qemu binary to use, the ``avocado_qemu``
package will automatically probe it. The probe will try to use the Qemu
binary from the git tree build directory, using the same architecture as
the local system (if the architecture is not specified). If the Qemu
binary is not available in the git tree build directory, the next try is
to use the system installed Qemu binary.

You can define a number of optional parameters, providing them via YAML
file using the Avocado parameters system:

- ``qemu_bin``: Use a given Qemu binary, skipping the automatic
  probe. Example: ``qemu_bin: /usr/libexec/qemu-kvm``.
- ``qemu_dst_bin``: Use a given Qemu binary to create the destination VM
  when the migration process takes place. If it's not provided, the same
  binary used in the source VM will be used for the destination VM.
  Example: ``qemu_dst_bin: /usr/libexec/qemu-kvm-binary2``.
- ``arch``: Probe the Qemu binary from a given architecture. It has no
  effect if ``qemu_bin`` is specified. If not provided, the binary probe
  will use the system architecture. Example: ``arch: x86_64``
- ``machine_type``: Use this option to define a machine type for the VM.
  Example: ``machine_type: pc``
- ``machine_accel``: Use this option to define a machine acceleration
  for the VM. Example: ``machine_accel: kvm``.
- ``machine_kvm_type``: Use this option to select the KVM type when the
  ``accel`` is ``kvm`` and there are more than one KVM types available.
  Example: ``machine_kvm_type: PR``

To use a parameters file, you have to install the yaml_to_mux plugin
(`python2-avocado-plugins-varianter-yaml-to-mux` on Fedora,
`avocado-framework-plugin-varianter-yaml-to-mux` on pip).

Run the test with::

    $ avocado run test_my_test.py -m parameters.yaml

Additionally, you can use a variants file to to set different values
for each parameter. Using the YAML tag ``!mux`` Avocado will execute the
tests once per combination of parameters. Example::

    $ cat variants.yaml
    qemu_bin: /usr/libexec/qemu-kvm
    architecture: !mux
        x86_64:
            arch: x86_64
        i386:
            arch: i386

Run it the with::

    $ avocado run test_my_test.py -m variants.yaml

See ``avocado run --help`` and ``man avocado`` for several other
options, such as ``--filter-by-tags``, ``--show-job-log``,
``--failfast``, etc.

Adding an Guest OS Image
------------------------

We have some APIs to help with the Guest OS Image management and use. To add
an image in your VM, you can call the ``add_image()`` method::

    from avocado_qemu import test

    class MyTest(test.QemuTest):
        """
        :avocado: enable
        """

        def setUp(self):
            image_path = '/var/lib/images/guestos.qcow2'
            user = 'root'
            pass = '123456'
            self.vm.add_image(image_path, user, pass)
            self.vm.args.extend(['-m', '512'])
            self.vm.launch()

If you don't have an Image, you can use the ``vmimage`` module from Avocado
Framework utils, which will download and cache a Cloud Image from your
preferred distro, according to the provided parameters. Example::

    >>> from avocado.utils import vmimage
    >>> image = vmimage.get('Fedora', arch='x86_64')
    >>> image
    <Image name=Fedora version=27 arch=x86_64>
    >>> image.path
    '/tmp/Fedora-Cloud-Base-27-1.6.x86_64-9853f34e.qcow2'

Refer to the ``vmimage`` documentation for more information:
http://avocado-framework.readthedocs.io/en/latest/utils/vmimage.html

If you're using the ``vmimage`` utility, you're getting a Cloud Image, which
requires the default user password to be set using CloudInit. To cope with
that requirement, the Avocado Qemu includes to the VM object the
``cloudinit()`` method. This simple API will attach to the VM a CDROM with the
required files containing the default user password, as set by the
``add_image()``. Putting all together::

    from avocado_qemu import test
    from avocado.utils import vmimage

    class MyTest(test.QemuTest):
        """
        :avocado: enable
        """

        def setUp(self):
            image = vmimage.get('Fedora')

            # Fedora Cloud Image comes with default user 'fedora'
            user = 'fedora'

            # Fedora Cloud Image password needs to be set using CouldInit
            pass = '123456'

            # vmimage.path is already a external snapshot
            # No need add the ',snapshot=on' to the disk
            self.vm.add_image(image.path, user, pass, snapshot=False)

            # Adding the CloudInit CDROM to set the password
            self.vm.cloudinit()

            self.vm.args.extend(['-m', '512'])
            self.vm.launch()

        ...

Adding a Qemu Machine
---------------------

If not using the parameters YAML file, which has precedence, you can add the
``-machine`` option to the Qemu command line using the ``add_machine()``
method. Example::

    from avocado_qemu import test

    class MyTest(test.QemuTest):
        """
        :avocado: enable
        """

        def setUp(self):
            self.vm.add_machine(machine_type='pc', machine_accel='kvm')

            self.vm.args.extend(['-m', '512'])
            self.vm.launch()

        ...

The call above will result in ``-machine pc,accel=kvm`` added to the Qemu
command line.
