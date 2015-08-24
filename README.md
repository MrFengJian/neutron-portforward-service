# 简介
  在OpenStack原生L3功能的基础上，基于router的外网网关功能实现了端口转发，支持TCP、UDP两种协议。  

  **优点：只需要增加两个配置项，不需要对原有代码做任何改动**。  

# 前提
  + 基于OpenStack Icehouse 2014-1-5 Ubuntu14.04版本的代码实现。  

  + 网络节点上了l3-agent或者vpn-agent来启用router功能。  

# 安装指南  

+ **1.服务端安装**  

在neutron-server所在节点，解压portforward.tar
修改server.sh中的
mysql_ip=
变量，指向数据库服务地址。
然后执行server.sh脚本，中间提示时，输入数据库中neutron用户的密码来增加数据库表。

+ **2.agent端安装**  

在l3-agent或者vpn-agent所在节点，解压portforward.tar
执行agent.sh，安装neutron-portforward-agent服务，并自动设置为开机启动。
日志为/var/log/neutron-portforward-agent.log。
