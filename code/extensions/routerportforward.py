# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2011 OpenStack Foundation
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from neutron.api import extensions
from neutron.openstack.common import log as logging
from neutron.plugins.common import constants
from neutron import manager
from oslo.config import cfg
from neutron import quota
from neutron.api.v2 import base

from neutron.services.skycloud import constants as skycloud_constants

LOG = logging.getLogger(__name__)

ROUTER_PORT_FORWARD_ATTRIBUTE = {
    "portforwards": {
        'id': {'allow_post': False, 'allow_put': False,
               'is_visible': True,
               'primary_key': True},
        'tenant_id': {'allow_post': True, 'allow_put': False,
                      'is_visible': True,
                      'primary_key': False},
        'name': {'allow_post': True, 'allow_put': True,
                 'is_visible': True,
                 'primary_key': False},
        'router_id': {'allow_post': True, 'allow_put': False,
                      'is_visible': True,
                      'primary_key': False},
        'router_gateway_ip': {'allow_post': True, 'allow_put': False,
                              'is_visible': True,
                              'primary_key': False},
        'instance_id': {'allow_post': True, 'allow_put': False,
                        'is_visible': True,
                        'primary_key': False},
        'instance_fix_ip': {'allow_post': True, 'allow_put': False,
                            'is_visible': True,
                            'primary_key': False},
        'source_port': {'allow_post': True, 'allow_put': False,
                        'is_visible': True,
                        'primary_key': False},
        'destination_port': {'allow_post': True, 'allow_put': False,
                             'is_visible': True,
                             'primary_key': False},
        'protocol': {'allow_post': True, 'allow_put': False,
                     'is_visible': True,
                     'primary_key': False}
    }
}


def build_plural_mappings(special_mappings, resource_map):
    plural_mappings = {}
    for plural in resource_map:
        singular = special_mappings.get(plural, plural[:-1])
        plural_mappings[plural] = singular
    return plural_mappings


def build_resource_info(plural_mappings, resource_map, which_service,
                        action_map=None, register_quota=False,
                        translate_name=False, allow_bulk=False):
    resources = []
    if not which_service:
        which_service = constants.CORE
    if action_map is None:
        action_map = {}
    if which_service != constants.CORE:
        plugin = manager.NeutronManager.get_service_plugins()[which_service]
    else:
        plugin = manager.NeutronManager.get_plugin()
    for collection_name in resource_map:
        resource_name = plural_mappings[collection_name]
        params = resource_map.get(collection_name, {})
        if translate_name:
            collection_name = collection_name.replace('_', '-')
        if register_quota:
            quota.QUOTAS.register_resource_by_name(resource_name)
        member_actions = action_map.get(resource_name, {})
        controller = base.create_resource(
            collection_name, resource_name, plugin, params,
            member_actions=member_actions,
            allow_bulk=allow_bulk,
            allow_pagination=cfg.CONF.allow_pagination,
            allow_sorting=cfg.CONF.allow_sorting)
        resource = extensions.ResourceExtension(
            collection_name,
            controller,
            path_prefix=skycloud_constants.PORT_FORWARD_PATH_PREFIX,
            member_actions=member_actions,
            attr_map=params)
        resources.append(resource)
    return resources


class Routerportforward(extensions.ExtensionDescriptor):
    @classmethod
    def get_name(cls):
        return "Port forwad service for router"

    @classmethod
    def get_alias(cls):
        return "routerportforward"

    @classmethod
    def get_description(cls):
        return "Routerportfoward"

    @classmethod
    def get_namespace(cls):
        return "http://docs.openstack.org/ext/flavor/api/v1.0"

    @classmethod
    def get_updated(cls):
        return "2012-07-20T10:00:00-00:00"

    @classmethod
    def get_resources(cls):
        plural_mappings = build_plural_mappings(
            {}, ROUTER_PORT_FORWARD_ATTRIBUTE)
        action_map = None
        return build_resource_info(plural_mappings,
                                   ROUTER_PORT_FORWARD_ATTRIBUTE,
                                   skycloud_constants.PORT_FORWARD_PLUGIN_NAME,
                                   action_map=action_map,
                                   register_quota=False)

    def get_extended_resources(self, version):
        return ROUTER_PORT_FORWARD_ATTRIBUTE
