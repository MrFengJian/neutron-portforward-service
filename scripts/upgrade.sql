use neutron;
DROP TABLE IF EXISTS `neutron`.`portforwards`;
CREATE TABLE `neutron`.`portforwards` (
  `id` varchar(36) NOT NULL,
  `name` varchar(100) DEFAULT NULL,
  `router_id` varchar(36) DEFAULT NULL,
  `router_gateway_ip` varchar(100) DEFAULT NULL,
  `instance_id` varchar(36) DEFAULT NULL,
  `instance_fix_ip` varchar(100) DEFAULT NULL,
  `source_port` varchar(10) DEFAULT NULL,
  `destination_port` varchar(10) DEFAULT NULL,
  `protocol` varchar(10) DEFAULT NULL,
  `tenant_id` varchar(36) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `router_id` (`router_id`),
  CONSTRAINT `portforwards_ibfk_1` FOREIGN KEY (`router_id`) REFERENCES `routers` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
