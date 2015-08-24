#!/bin/bash
echo "step 1:copy package code"
. ./scripts/copy_code.sh
echo "step 2:config agent service"

echo '# vim:set ft=upstart ts=2 et:
description "Neutron PortForward Agent"
author "Fengjj fengjj@chinaskycloud.com"

start on runlevel [2345]
stop on runlevel [!2345]

respawn

chdir /var/run

pre-start script
  mkdir -p /var/run/neutron
  chown neutron:root /var/run/neutron
  # Check to see if openvswitch plugin in use by checking
  # status of cleanup upstart configuration
  if status neutron-ovs-cleanup; then
    start wait-for-state WAIT_FOR=neutron-ovs-cleanup WAIT_STATE=running WAITER=neutron-portforward-agent
  fi
end script

exec start-stop-daemon --start --chuid neutron --exec /usr/bin/neutron-portforward-agent -- \
       --config-file=/etc/neutron/neutron.conf --log-file=/var/log/neutron/portforward_agent.log
' > /etc/init/neutron-portforward-agent.conf 

cp ./scripts/neutron-portforward-agent /usr/bin/neutron-portforward-agent

ln -s /lib/init/upstart-job /etc/init.d/neutron-portforward-agent
update-rc.d neutron-portforward-agent defaults 30

echo "successfully installed neutron-portforward-agent"
