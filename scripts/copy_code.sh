#!/bin/bash
NEUTRON_LIB_DIR="/usr/lib/python2.7/dist-packages/neutron/"
cp -r ./code/db/* $NEUTRON_LIB_DIR/db/
cp -r ./code/extensions/* $NEUTRON_LIB_DIR/extensions/
cp -r ./code/services/* $NEUTRON_LIB_DIR/services 

