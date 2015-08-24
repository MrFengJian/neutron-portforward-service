from neutron.openstack.common import log as logging
import sqlalchemy as sa
from sqlalchemy.orm import exc

from neutron.db import model_base
from neutron.db import models_v2
from neutron.db.l3_db import Router

from neutron.openstack.common import uuidutils
from eventlet import greenthread
from neutron.common import exceptions
from neutron.openstack.common.gettextutils import _
from neutron.db import db_base_plugin_v2

LOG = logging.getLogger(__name__)


class PortForwardNotFound(exceptions.NotFound):
    message = _("port forward rule with %(id)s do not exist!")


class InvalidProtocol(exceptions.BadRequest):
    message = _("invalid protocol type %(protocol)s.valid value is TCP or UDP.")


class RouterUnavailable(exceptions.ServiceUnavailable):
    message = _("router %(router)s is not available due to admin state is Down or has no external gateway.")


class PortNotFoundByIp(exceptions.NotFound):
    message = _("port with device id %(device_id)s and ip %(ip_address)s is not found by ip_adress or subnet")


class PortUnavailable(exceptions.ServiceUnavailable):
    message = _("port %(port)s is not ACTIVE for port forward.")


class PortNotFound(exceptions.NotFound):
    message = _("port with device id %(device_id)s is not found by ip_adress or subnet")


class PortforwardExisted(exceptions.Conflict):
    message = _("portforward rule with same source %(router_id)s and %(source_port)s already exists.")


class PortNotFoundBySubnet(exceptions.NotFound):
    message = _("port with device id %(device_id)s and subnetid %(subnet_id)s is not found by ip_adress or subnet")


class RouterSubnetUnconnected(exceptions.BadRequest):
    message = _("router %(router_id) is not connected with subnet of %(instance_id)s fixed ip address %(ip_address)s")


# DB model
class PortForward(model_base.BASEV2, models_v2.HasId):
    name = sa.Column(sa.String(100))
    router_id = sa.Column(sa.String(36), sa.ForeignKey('routers.id'))
    router_gateway_ip = sa.Column(sa.String(100))
    instance_id = sa.Column(sa.String(36))
    instance_fix_ip = sa.Column(sa.String(100))
    source_port = sa.Column(sa.String(10))
    destination_port = sa.Column(sa.String(10))
    protocol = sa.Column(sa.String(10))
    tenant_id = sa.Column(sa.String(36))
    # applied=sa.Column(sa.Boolean)


# query and db method will call db_base_plugin_v2.CommonDbMixin in other type
class RouterPortForwardDbMixin(db_base_plugin_v2.CommonDbMixin):
    def get_portforwards(self, context, fields=None, filters=None):
        return self._get_collection(context, PortForward,
                                    self._make_portfoward_dict,
                                    filters=filters, fields=fields)

    def get_portforward(self, context, id, fields=None):
        portforward = self._get_portforward(context, id)
        return self._make_portfoward_dict(portforward, fields)

    def _get_portforward(self, context, id):
        try:
            portforward = self._get_by_id(context, PortForward, id)
        except exc.NoResultFound, e:
            raise PortForwardNotFound(id=id)
        return portforward

    def delete_portforward(self, context, id):
        portforward = None
        with context.session.begin(subtransactions=True):
            portforward = self._get_portforward(context, id)
            context.session.delete(portforward)
        greenthread.spawn_n(self._delete_portforward, context, portforward)

    def update_portforward(self, context, id, portforward):
        portforward_data = portforward['portforward']
        with context.session.begin(subtransactions=True):
            portforward_db = self._get_portforward(context, id)
            portforward_db.update(portforward_data)
        return self._make_portfoward_dict(portforward_db)

    def create_portforward(self, context, **kargs):
        portforward = kargs["portforward"]["portforward"]
        id = uuidutils.generate_uuid()
        self.validate_portforward(context, portforward)
        with context.session.begin(subtransactions=True):
            res = {
                "id": id,
                "name": portforward["name"],
                "router_id": portforward["router_id"],
                "router_gateway_ip": portforward["router_gateway_ip"],
                "instance_id": portforward["instance_id"],
                "instance_fix_ip": portforward["instance_fix_ip"],
                "source_port": portforward["source_port"],
                "destination_port": portforward["destination_port"],
                "protocol": portforward["protocol"],
                "tenant_id": portforward["tenant_id"]
            }
            portforward_db = PortForward(**res)
            context.session.add(portforward_db)
            greenthread.sleep(0)
        portforward = self.get_portforward(context, id)
        greenthread.spawn_n(self.apply_portforward, context, portforward)
        return portforward

    def _make_portfoward_dict(self, portforward, fields=None):
        res = {"id": portforward["id"],
               "name": portforward["name"],
               "router_id": portforward["router_id"],
               "router_gateway_ip": portforward["router_gateway_ip"],
               "instance_id": portforward["instance_id"],
               "instance_fix_ip": portforward["instance_fix_ip"],
               "source_port": portforward["source_port"],
               "destination_port": portforward["destination_port"],
               "protocol": portforward["protocol"],
               "tenant_id": portforward["tenant_id"]}
        return self._fields(res, fields)

    def validate_portforward(self, context, portforward):
        protocol = portforward["protocol"]
        protocol = protocol.upper()
        if protocol != "TCP" and protocol != "udp":
            raise InvalidProtocol(protocol=portforward["protocol"])
        router_id = portforward["router_id"]
        source_port = portforward["source_port"]
        router = self.get_router(context, router_id)
        if not router["admin_state_up"]:
            raise RouterUnavailable(router=router)
        # if router is not set gateway
        if not router["gw_port_id"]:
            raise RouterUnavailable(router=router)
        router_gateway_ip = portforward["router_gateway_ip"]
        router_gateway_port = self.get_port(context, router_id, ip_address=router_gateway_ip)
        # router gateway port is always down
        instance_id = portforward["instance_id"]
        instance_fix_ip = portforward["instance_fix_ip"]
        instance_port = self.get_port(context, instance_id, ip_address=instance_fix_ip)
        if not instance_port:
            raise PortNotFoundByIp(device_id=instance_id, ip_address=instance_fix_ip)
        if instance_port["status"] != "ACTIVE":
            raise PortUnavailable(port=instance_port)
        # check router and instance subnet connectivity
        instance_subnet = None
        for fip in instance_port["fixed_ips"]:
            if instance_fix_ip == fip["ip_address"]:
                instance_subnet = fip["subnet_id"]
        router_subnet_port = self.get_port(context, router_id, subnet_id=instance_subnet)
        if not router_subnet_port:
            raise PortNotFoundBySubnet(device_id=router_id, subnet_id=instance_subnet)
        if router_subnet_port["status"] != "ACTIVE":
            raise RouterSubnetUnconnected(router_id=router_id, instance_id=instance_id, ip_address=instance_fix_ip)
        if self.check_existed(context, portforward):
            raise PortforwardExisted(router_id=router_id, source_port=source_port)

    def get_port(self, context, device_id, ip_address=None, subnet_id=None):
        query = self._model_query(context, models_v2.Port)
        try:
            ports = query.filter(models_v2.Port.device_id == device_id)
            for port in ports:
                fixed_ips = port["fixed_ips"]
                for fixed_ip in fixed_ips:
                    if ip_address and ip_address == fixed_ip["ip_address"]:
                        return port
                    if subnet_id and subnet_id == fixed_ip["subnet_id"]:
                        return port
            return None
        except exc.NoResultFound:
            raise PortNotFound(device_id=device_id)

    def get_router(self, context, router_id):
        try:
            router = self._get_by_id(context, Router, router_id)
        except exc.NoResultFound:
            raise l3.RouterNotFound(router_id=router_id)
        return router

    def check_existed(self, context, portforward):
        query = self._model_query(context, PortForward)
        try:
            rules = query.filter(PortForward.source_port == portforward["source_port"]). \
                filter(PortForward.router_id == portforward["router_id"])
            for rule in rules:
                return True
            return False
        except exc.NoResultFound:
            return False
        return False
