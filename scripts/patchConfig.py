#!/usr/bin/env python
#coding=utf-8
'''
最好在Python2.7以上，否则会导致生成的问题配置乱序，但配置文件最终仍然可以使用。
'''
import  ConfigParser

try:
    import collections
    dict_type=collections.OrderedDict
except:
    dict_type=dict

DEFAULT_SECTION="DEFAULT"

def patch_config(patch_file,config_file,same_modify=True,seperator=","):
    old_config = ConfigParser.ConfigParser(dict_type=dict_type)
    old_config.optionsxform=str
    old_config.read(config_file)
    patch_config=ConfigParser.ConfigParser(dict_type=dict_type)
    patch_config.read(patch_file)
    old_sections=old_config.sections()
    patch_sections=patch_config.sections()
    old_default_opts=old_config.defaults()
    patch_default_opts=patch_config.defaults()
    added_sections=[i for i in patch_sections if i not in old_sections]
    added_default_opts=[i for i in patch_default_opts if i not in old_default_opts]
    for  section in added_sections:
           patch_opts=patch_config.options(section)
           old_config.add_section(section)
           for opt in patch_opts:
                #skip config inherited from DEFAULT section
                if opt in patch_default_opts:
                    continue
                value=patch_config.get(section,opt)
                old_config.set(section,opt,value)
    for opt in added_default_opts:
        value=patch_config.get(DEFAULT_SECTION,opt)
        old_config.set(DEFAULT_SECTION,opt,value)
    modified_default_opts=set(patch_default_opts)-set(added_default_opts)
    for opt in modified_default_opts:
        old_value=old_config.get(DEFAULT_SECTION,opt)
        patch_value=patch_config.get(DEFAULT_SECTION,opt)
        if same_modify:
            old_config.set(DEFAULT_SECTION,opt,old_value+seperator+patch_value)
        else:
            old_config.set(DEFAULT_SECTION,opt,patch_value)
    modified_sections=set(patch_sections)-set(added_sections)
    for section in modified_sections:
        patch_opts=patch_config.options(section)
        old_opts=old_config.options(section)
        added_opts=set(patch_opts)-set(old_opts)
        for opt in added_opts:
            value=patch_config.get(section,opt)
            old_config.set(section,opt,value)
        modified_opts=set(patch_opts)-added_opts
        for opt in modified_opts:
            #skip config inherited from DEFAULT section
            if opt in patch_default_opts:
                continue
            old_value=old_config.get(section,opt)
            patch_value=patch_config.get(section,opt)
            if same_modify:
                old_config.set(section,opt,old_value+seperator+patch_value)
            else:
                old_config.set(section,opt,patch_value)

    old_config.write(open(config_file,"w"))

if __name__=="__main__":
    import sys
    patch_file,config_file=sys.argv[1:]
    patch_config(patch_file,config_file)
