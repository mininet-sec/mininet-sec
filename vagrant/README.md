# Mininet-Sec using [vagrant](https://www.vagrantup.com/).

### [RECOMMENDED] Mininet-Sec Vagrant Box

We have a Mininet-Sec pre-installed in a vagrant box. The box can be found [here](https://app.vagrantup.com/italovalcy/boxes/mininet-sec). For suggested Mininet-Sec resource allocation,
Here's an example [`Vagrantfile`](https://github.com/mininet-sec/mininet-sec/tree/main/vagrant/Vagrantfile):
```ruby
# -*- mode: ruby -*-
# vi: set ft=ruby :
Vagrant.configure("2") do |config|
  config.vm.box = "italovalcy/mininet-sec"
  config.vm.provider "virtualbox" do |vb|
    vb.memory = "4096"
    vb.cpus = "4"
    vb.name = "mininet-sec"
  end
end
```
----

### [NOT RECOMMENDED] Building from scratch with `vagrant` and VirtualBox containing Mininet-Sec

* Download and install VirtualBox and Vagrant
  * https://www.vagrantup.com/downloads
  * https://www.virtualbox.org/wiki/Downloads
* To create and start fresh virtual machine:
  * Create a file called "Vagrantfile" with this basic setup:
    ```ruby
    # -*- mode: ruby -*-
    # vi: set ft=ruby :
    Vagrant.configure("2") do |config|
      config.vm.box = "generic/debian11"
      config.disksize.size = '40GB'
      config.vm.provider "virtualbox" do |vb|
        vb.memory = 4096
        vb.cpus = 4
        vb.name = "mininet-sec"
      end
    end
    ```
  * Open your terminal or command line in the directory that has Vagrantfile
  * Start the virtual machine with,
    `$ vagrant up`
  * (If required) The username/password for the vm are both `vagrant`.

* Install your favorite graphical user interface (we deployed LXDE)

* To install Mininet-Sec, use the following commands:
    ```bash
    git clone https://github.com/mininet-sec/mininet-sec
    cd mininet-sec
    ./install.sh
    ```
* To test mininet-sec:
    * while still in the `mininet-sec` directory, enter
      ```bash
      sudo python2 examples/firewall.py
      ```
    * If it worked, You will see the Mininet-Sec CLI. Enter `exit` to close the CLI.

(Additional optional "not really needed" steps)
* To clean and export vm as Vagrant Box:
    * while in vm, enter these to clean:
      ```bash
      cd
      sudo apt-get clean
      sudo dd if=/dev/zero of=/EMPTY bs=1M
      sudo rm -f /EMPTY
      cat /dev/null > ~/.bash_history && history -c && exit
      ```
    * Close the vm window and open a terminal in the same directory as the `Vagrantfile`.
    * In the terminal, type this command where `vb_name` is the name of the vm defined in `Vagrantfile`, and `box_name` any name for the output `.box` file
      ```bash
      vagrant package --base vb_name --output box_name.box
      ```
