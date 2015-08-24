from neutron import manager
from neutron.services.skycloud import constants as skycloud_constants
import eventlet
from neutron import context
from neutron.openstack.common import log as logging
from oslo.config import cfg
from neutron.agent.common import config
from neutron.common import legacy
from neutron import service as neutron_service
from neutron.openstack.common import service
from neutron.agent import l3_agent
from neutron.agent.linux import ip_lib
from neutron.agent.linux import iptables_manager
from neutron.agent.linux import utils as linux_utils
from neutron.openstack.common import periodic_task
from neutron.openstack.common import lockutils
from neutron.openstack.common.gettextutils import _

LOG = logging.getLogger(__name__)
NS_PREFIX = l3_agent.NS_PREFIX
from neutron.openstack.common.rpc import proxy


class PortForwardPluginApi(proxy.RpcProxy):
    """API for plugin to call portforward agent."""
    BASE_RPC_API_VERSION = '1.0'

    def __init__(self, topic, host):
        super(PortForwardPluginApi, self).__init__(
            topic=topic, default_version=self.BASE_RPC_API_VERSION)
        self.topic = topic
        self.host = host

    def get_portforwards(self, context):
        return self.call(context, self.make_msg("sync_portforwards", host=self.host), topic=self.topic)


class RouterInfo(object):
    def __init__(self, router_id, root_helper, use_namespaces=True):
        self.ns_name = NS_PREFIX + router_id if use_namespaces else None
        self.router_id = router_id
        self.root_helper = root_helper
        self.iptables_manager = iptables_manager.IptablesManager(
            root_helper=root_helper,
            namespace=self.ns_name)


class PortForwardAgent(manager.Manager):
    def __init__(self, host, conf=None):
        self.plugin_rpc = PortForwardPluginApi(skycloud_constants.PORT_FORWARD_PLUGIN_TOPIC, host)
        self.fullsync = True
        self.applied_rules = set()
        self.handling_rules = set()
        self.routers = {}

    def delete_portforward(self, ctxt, **kwargs):
        LOG.debug("got a rpc request _delete_portforward %s" % (kwargs))
        cxt = context.get_admin_context()
        portforward = kwargs["portforward"]
        router_id = portforward["router_id"]
        port_forward_id = portforward["id"]
        ri = self.routers.get(router_id)
        manual_delete = False
        if ri:
            result = ri.portforwards.pop(port_forward_id, None)
            # rule is not applied on router
            if not result:
                manual_delete = True
        else:
            manual_delete = True
            root_helper = "sudo /usr/bin/neutron-rootwrap /etc/neutron/rootwrap.conf"
            ri = RouterInfo(router_id, root_helper)
            ri.portforwards = {}
            self.routers[router_id] = ri
        if not manual_delete:
            self._process_ri_rules(context, ri)
        else:
            if not self.is_router_namespace_exists(ri):
                LOG.info("portforward 's router namespace doesn't exist,nothing need to do")
                return
            root_helper = ri.iptables_manager.root_helper
            router_gateway_ip = portforward["router_gateway_ip"]
            source_port = portforward["source_port"]
            instance_fix_ip = portforward["instance_fix_ip"]
            destination_port = portforward["destination_port"]
            protocol = portforward["protocol"]
            for chain, rule in self.get_delete_port_forward_rules(router_gateway_ip, source_port, instance_fix_ip,
                                                                  destination_port, protocol):
                args = ['ip', 'netns', 'exec', ri.iptables_manager.namespace] + "iptables -t nat ".split() + ["-D",
                                                                                                              chain] + rule.split()
                LOG.debug("manual delete porforward rules args %s" % (args))
                linux_utils.execute(args, root_helper=root_helper)

    def apply_portforward(self, ctxt, **kwargs):
        LOG.debug("got a rpc request _apply_portforward %s" % (kwargs))
        contxt = context.get_admin_context()
        portforward = kwargs["portforward"]
        router_id = portforward["router_id"]
        self._apply_portforward_rules_on_router(contxt, router_id, [portforward])

    @periodic_task.periodic_task
    @lockutils.synchronized('portforward-agent', 'neutron-')
    def sync_portforwards(self, context):
        LOG.debug(_("Starting sync_portforwards - fullsync:%s"),
                  self.fullsync)
        if not self.fullsync:
            return
        try:
            portforwards = self.plugin_rpc.get_portforwards(context)
            data = {}
            for portforward in portforwards:
                router_id = portforward["router_id"]
                if router_id not in data:
                    data[router_id] = [portforward]
                else:
                    data[router_id].append(portforward)
            for router_id, portforwards in data.iteritems():
                self._apply_portforward_rules_on_router(context, router_id, portforwards)
        except Exception,e:
            self.fullsync=True
        self.fullsync = False
        LOG.debug(_("finish sync_portforwards - fullsync:%s"),
                  self.fullsync)

    def _process_ri_rules(self, context, ri):
        try:
            ri.iptables_manager.ipv4['nat'].clear_rules_by_tag("port_forward")
        except Exception, e:
            LOG.debug(_("Error during clear rules by tag port forward  %(e)s"),
                      {"e": e})
        LOG.debug("port forward agent is handling portforwards %s on router %s"%(ri.portforwards,ri.router_id))
        for port_forward_id, portforward in ri.portforwards.iteritems():
            router_gateway_ip = portforward["router_gateway_ip"]
            source_port = portforward["source_port"]
            instance_fix_ip = portforward["instance_fix_ip"]
            destination_port = portforward["destination_port"]
            protocol = portforward["protocol"]
            for chain, rule in self.get_port_forward_rules(router_gateway_ip, source_port, instance_fix_ip,
                                                           destination_port, protocol):
                ri.iptables_manager.ipv4['nat'].add_rule(chain, rule, tag="port_forward")
            self.applied_rules.add(port_forward_id)

        # if thereis no namespace,skip this turn.
        if not self.is_router_namespace_exists(ri):
            LOG.warn("network namespace %s doesn't exists.skip apply porforwards." % (ri.ns_name))
            return
        ri.iptables_manager.apply()
        LOG.debug("successfully apply port_forward rules on router with id %s" % (ri.router_id))

    def is_router_namespace_exists(self,ri):
        ip_wrapper_root = ip_lib.IPWrapper(ri.root_helper)
        return ip_wrapper_root.netns.exists(ri.ns_name)

    def _apply_portforward_rules_on_router(self, context, router_id, portforwards):
        LOG.debug("begin to apply port_forward rule %s" % (portforwards))
        ri = self.routers.get(router_id)
        if not ri:
            root_helper = "sudo /usr/bin/neutron-rootwrap /etc/neutron/rootwrap.conf"
            ri = RouterInfo(router_id, root_helper, portforwards)
            ri.portforwards = {}
        self.routers[router_id] = ri
        try:
            ri.iptables_manager.ipv4['nat'].clear_rules_by_tag("port_forward")
        except Exception, e:
            LOG.debug(_("Error during sync port forward  %(e)s"),
                      {"e": e})
        for portforward in portforwards:
            port_forward_id = portforward["id"]
            ri.portforwards[port_forward_id] = portforward

        self._process_ri_rules(context, ri)

        """
    original command
     "iptables -t nat -A PREROUTING -d %s -p tcp -m tcp --dport %s -j DNAT --to-destination %s:%s"%(
          router_gateway_ip,source_port,instance_fix_ip,destination_port)
    "iptables -t nat -A POSTROUTING -d %s -p tcp -m tcp --dport %s -j SNAT --to-source %s"%(
        instance_fix_ip,destination_port,router_gateway_ip)
    """

    def get_port_forward_rules(self, router_gateway_ip, source_port, instance_fix_ip, destination_port, protocol):
        protocol = protocol.lower()
        return [("PREROUTING", "-d %s -p %s -m %s --dport %s -j DNAT --to-destination %s:%s" % (
            router_gateway_ip, protocol, protocol, source_port, instance_fix_ip, destination_port)),
                ("POSTROUTING", "-d %s -p %s -m %s --dport %s -j SNAT --to-source %s" % (
                    instance_fix_ip, protocol, protocol, destination_port, router_gateway_ip))
                ]

    """
    original command
     "iptables -t nat -D PREROUTING -d %s -p tcp -m tcp --dport %s -j DNAT --to-destination %s:%s"%(
          router_gateway_ip,source_port,instance_fix_ip,destination_port)
    "iptables -t nat -D POSTROUTING -d %s -p tcp -m tcp --dport %s -j SNAT --to-source %s"%(
        instance_fix_ip,destination_port,router_gateway_ip)
    """

    def get_delete_port_forward_rules(self, router_gateway_ip, source_port, instance_fix_ip, destination_port,
                                      protocol):
        protocol = protocol.lower()
        return [("neutron-portforw-PREROUTING", "-d %s -p %s -m %s --dport %s -j DNAT --to-destination %s:%s" % (
            router_gateway_ip, protocol, protocol, source_port, instance_fix_ip, destination_port)),
                ("neutron-portforw-POSTROUTING", "-d %s -p %s -m %s --dport %s -j SNAT --to-source %s" % (
                    instance_fix_ip, protocol, protocol, destination_port, router_gateway_ip))
                ]


def main(manager="neutron.services.skycloud.portforward_agent.PortForwardAgent"):
    eventlet.monkey_patch()
    conf = cfg.CONF
    conf(project='neutron')
    config.setup_logging(conf)
    legacy.modernize_quantum_config(conf)
    server = neutron_service.Service.create(
        binary='neutron-portforward-agent',
        topic=skycloud_constants.PORT_FORWARD_AGENT_TOPIC,
        report_interval=60, host=conf.host,
        manager=manager)
    service.launch(server).wait()
