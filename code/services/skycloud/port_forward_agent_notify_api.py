# Copyright (c) 2013 OpenStack Foundation.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from neutron import manager
from neutron.openstack.common import log as logging
from neutron.openstack.common.rpc import proxy
from neutron.plugins.common import constants as service_constants
from neutron.services.skycloud import constants as skycloud_constants
from neutron.openstack.common.gettextutils import _

LOG = logging.getLogger(__name__)


class PortForwardAgentNotifyAPI(proxy.RpcProxy):
    """API for plugin to notify portforward agent."""
    BASE_RPC_API_VERSION = '1.0'

    def __init__(self, topic=skycloud_constants.PORT_FORWARD_AGENT_TOPIC):
        super(PortForwardAgentNotifyAPI, self).__init__(
            topic=topic, default_version=self.BASE_RPC_API_VERSION)

    def apply_portforward(self,context,portforward):
        LOG.debug("try to apply port forward rules %s"%(portforward))
        router_id=portforward["router_id"]
        adminContext = context.is_admin and context or context.elevated()
        plugin = manager.NeutronManager.get_service_plugins().get(
            service_constants.L3_ROUTER_NAT)
        l3_agents = plugin.get_l3_agents_hosting_routers(
            adminContext, [router_id],
            admin_state_up=True,
            active=True)
        for l3_agent in l3_agents:
            method="apply_portforward"
            LOG.debug(_('Notify agent at %(topic)s.%(host)s the message '
                        '%(method)s'),
                      {'topic': skycloud_constants.PORT_FORWARD_AGENT_TOPIC,
                       'host': l3_agent.host,
                       'method': method})
            topic='%s.%s' % (skycloud_constants.PORT_FORWARD_AGENT_TOPIC, l3_agent.host)
            self.cast(
                context, self.make_msg(method,portforward=portforward),
                topic=topic,
                version=self.BASE_RPC_API_VERSION)

    def delete_portforward(self,context,portforward):
        LOG.debug("try to delete portforward %s"%(portforward))
        router_id=portforward["router_id"]
        adminContext = context.is_admin and context or context.elevated()
        plugin = manager.NeutronManager.get_service_plugins().get(
            service_constants.L3_ROUTER_NAT)
        l3_agents = plugin.get_l3_agents_hosting_routers(
            adminContext, [router_id],
            admin_state_up=True,
            active=True)
        for l3_agent in l3_agents:
            method="delete_portforward"
            LOG.debug(_('Notify agent at %(topic)s.%(host)s the message '
                        '%(method)s'),
                      {'topic': skycloud_constants.PORT_FORWARD_AGENT_TOPIC,
                       'host': l3_agent.host,
                       'method': method})
            topic='%s.%s' % (skycloud_constants.PORT_FORWARD_AGENT_TOPIC, l3_agent.host)
            self.cast(
                context, self.make_msg(method,portforward=portforward),
                topic=topic,
                version=self.BASE_RPC_API_VERSION)


AgentNotify = PortForwardAgentNotifyAPI()
