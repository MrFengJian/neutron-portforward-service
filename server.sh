#!/bin/bash
echo "step1:copy package code"

mysql_ip=192.168.100.204

. ./scripts/copy_code.sh

echo "step2:modify neutron server config"
entry_point_path=$(ls /usr/lib/python2.7/dist-packages/neutron*.egg-info/entry_points.txt)
neutron_conf_path="/etc/neutron/neutron.conf"

cp $neutron_conf_path "$neutron_conf_path-bak"
cp $entry_point_path  "$entry_point_path-bak"

python ./scripts/patchNeutron.py

python ./scripts/patchConfig.py ./config/entry_points_patch.txt $entry_point_path

echo "step3:update db tables"

echo "please input db user:neutron 's password "
mysql -uneutron -p  < ./scripts/upgrade.sql

echo "step 3:restart neturon-server service"
sleep 1
service neutron-server restart

echo "successfully installed portforward server"
