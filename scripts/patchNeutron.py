#!/usr/bin/env python
#coding=utf-8

def patch():
   config="/etc/neutron/neutron.conf"
   with open("/etc/neutron/neutron.conf") as conf:
      contents=conf.readlines()
   result=[]
   for line in contents:
      if line.startswith("service_plugins"):
          line=line.strip()+",portforward\n"
      result.append(line)
   with open("/etc/neutron/neutron.conf","w") as conf:
      conf.writelines(result)

if __name__=="__main__":
   patch()
