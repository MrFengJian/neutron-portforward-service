#!/bin/bash

entry_point_path=$(ls /usr/lib/python2.7/dist-packages/neutron*.egg-info/entry_points.txt)
neutron_conf_path="/etc/neutron/neutron.conf"

cp "$neutron_conf_path-bak"  $neutron_conf_path
cp "$entry_point_path-bak"   $entry_point_path
