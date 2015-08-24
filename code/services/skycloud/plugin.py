# vim: tabstop=4 shiftwidth=4 softtabstop=4

# copywright skycloud
from oslo.config import cfg
from neutron.services.service_base import ServicePluginBase
from neutron.db import portforward_db
from neutron.services.skycloud import port_forward_agent_notify_api
from neutron.services.skycloud import constants as skycloud_constants
from neutron.openstack.common import rpc
from neutron.common import rpc as q_rpc
from neutron import context as neutron_context
from neutron.common import constants
from neutron.openstack.common.gettextutils import _
from neutron.openstack.common import log as logging
from neutron.openstack.common import jsonutils
from neutron.extensions import portbindings
from neutron import manager
from neutron.plugins.common import constants as plugin_constants
from neutron.common import utils
LOG = logging.getLogger(__name__)


class PortForwardPluginRpcCallbacks(portforward_db.RouterPortForwardDbMixin):
    RPC_API_VERSION = '1.0'

    def sync_portforwards(self, context, **kwargs):
        host = kwargs["host"]
        adminContext = neutron_context.get_admin_context()
        portforwards = self.get_portforwards(adminContext)
        router_ids=None
        l3plugin = manager.NeutronManager.get_service_plugins()[
            plugin_constants.L3_ROUTER_NAT]
        if not l3plugin:
            routers = {}
            LOG.error(_('No plugin for L3 routing registered! Will reply '
                        'to l3 agent with empty router dictionary.'))
        elif utils.is_extension_supported(
                l3plugin, constants.L3_AGENT_SCHEDULER_EXT_ALIAS):
            if cfg.CONF.router_auto_schedule:
                l3plugin.auto_schedule_routers(context, host, router_ids)
            routers = l3plugin.list_active_sync_routers_on_active_l3_agent(
                context, host, router_ids)
        else:
            routers = l3plugin.get_sync_data(context, router_ids)
        plugin = manager.NeutronManager.get_plugin()
        if utils.is_extension_supported(
            plugin, constants.PORT_BINDING_EXT_ALIAS):
            self._ensure_host_set_on_ports(context, plugin, host, routers)
        found_router_ids=[]
        for router in routers:
            found_router_ids.append(router["id"])
        portforwards=[portforward for portforward in  portforwards if portforward["router_id"] in found_router_ids ]
        LOG.debug(_("portforwards returned to port forward agent:\n %s"),
                  jsonutils.dumps(portforwards, indent=5))
        return portforwards

    def _ensure_host_set_on_ports(self, context, plugin, host, routers):
        for router in routers:
            LOG.debug(_("Checking router: %(id)s for host: %(host)s"),
                      {'id': router['id'], 'host': host})
            self._ensure_host_set_on_port(context, plugin, host,
                                          router.get('gw_port'))
            for interface in router.get(constants.INTERFACE_KEY, []):
                self._ensure_host_set_on_port(context, plugin, host,
                                              interface)

    def _ensure_host_set_on_port(self, context, plugin, host, port):
        if (port and
                (port.get(portbindings.HOST_ID) != host or
                         port.get(portbindings.VIF_TYPE) ==
                         portbindings.VIF_TYPE_BINDING_FAILED)):
            plugin.update_port(context, port['id'],
                               {'port': {portbindings.HOST_ID: host}})

    def create_rpc_dispatcher(self):
        """Get the rpc dispatcher for this manager.

        If a manager would like to set an rpc API version, or support more than
        one class as the target of rpc messages, override this method.
        """
        return q_rpc.PluginRpcDispatcher([self])


class PortForwardPlugin(ServicePluginBase, portforward_db.RouterPortForwardDbMixin):
    supported_extension_aliases = ["routerportforward"]

    def __init__(self):
        self.setup_rpc()

    def setup_rpc(self):
        self.topic = skycloud_constants.PORT_FORWARD_PLUGIN_TOPIC
        self.rpc_api = port_forward_agent_notify_api.AgentNotify
        self.agent_notifiers = {skycloud_constants.PORT_FORWARD_AGENT: self.rpc_api}
        self.conn = rpc.create_connection(new=True)
        self.callbacks = PortForwardPluginRpcCallbacks()
        self.dispatcher = self.callbacks.create_rpc_dispatcher()
        self.conn.create_consumer(self.topic, self.dispatcher,
                                  fanout=False)
        self.conn.consume_in_thread()

    def get_plugin_type(self):
        return skycloud_constants.PORT_FORWARD

    def get_plugin_name(self):
        return skycloud_constants.PORT_FORWARD_PLUGIN

    def get_plugin_description(self):
        return "Neutron PortForward Service Plugin"

    def apply_portforward(self, context, portforward):
        self.rpc_api.apply_portforward(context, portforward)

    def _delete_portforward(self, context, portforward):
        self.rpc_api.delete_portforward(context, portforward)
