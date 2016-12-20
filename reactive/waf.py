import os
import re
import subprocess
import base64
from functools import reduce
from charms.reactive import when, when_not, set_state, hook, remove_state
from charmhelpers.core.hookenv import (
    open_port,
    close_port,
    log,
    config as orig_config_get,
    relation_set,
    unit_get,
    status_set,
    in_relation_hook,
    relation_types,
    relation_ids
)
from charmhelpers.core.host import service_reload, service_start, service_stop
from charms.reactive.helpers import data_changed
from charmhelpers.core.templating import render
import pprint


@when('apache.start')
@when('waf.available')
@when_not('apache.started')
def start_apache():
    status_set('maintenance', 'Starting Apache')
    assert service_start('apache2'), 'Failed to start Apache2'
    set_state('apache.started')


@when('apache.started')
def started():
    status_set('active', 'Ready')


@when('apache.available')
@when_not('apache.started')
def setup_apache():
    status_set('maintenance', 'Setting up Apache')
    enable_module('security2')
    enable_module('proxy')
    enable_module('rewrite')
    enable_module('proxy_http')
    enable_module('proxy_html')
    enable_module('ssl')
    enable_module('syslog')
    # Empty unused ports.conf
    if os.path.exists('/etc/apache2/ports.conf'):
        open('/etc/apache2/ports.conf', 'w').write('')
    status_set('waiting', 'Waiting for relatioons to join')
    set_state('apache.start')


@when('apache.changed')
@when('apache.available')
def reload_apache():
    log('apache.changed Reloading apache')
    service_reload('apache2')
    remove_state('apache.changed')


@hook('{requires:http}-relation-{joined,changed}')
def setup_backend(backend):
    if not in_relation_hook():
        return
    relation_name = backend.relation_name
    service = relation_name[:relation_name.rindex('-backend')]  # Slice -backend
    log("Backend {} available".format(service))
    write_vhost(backend, service)
    open_port(orig_config_get()[service + '_port'], protocol='TCP')

    # Set available once the first relation joined. Simple but works
    set_state('waf.available')


# Backend relation departed. Delte vhost file
@hook('{requires:http}-relation-{departed,broken}')
def stop_backend(backend):
    relation_name = backend.relation_name
    service = relation_name[:relation_name.rindex('-backend')]  # Slice -backend
    log('A unit has left {}'.format(service))
    if(hosts_for_backend(backend)):
        write_vhost(backend, service)
    else:
        log("All units are gone. Stopping backend {}".format(service))
        try:
            os.remove('/etc/apache2/sites-enabled/{}.conf'.format(service))
        except FileNotFoundError:
            pass
        close_port(orig_config_get()[service + '_port'], protocol='TCP')
        set_state('apache.changed')


# Frontend became available. Set the port in the conversation.
@hook('{provides:http}-relation-{joined,changed}')
def setup_frontend(frontend):
    config = orig_config_get()
    relation_name = frontend.relation_name
    frontend.configure(config[relation_name + '_port'])


# This will save all config options into files
@when('config.changed')
def write_waf_config():
    write_file_from_option(
        '/etc/modsecurity/waf.conf',
        'securityrules',
        remove_if_empty=True,
        banner=True
        )
    write_file_from_option(
        '/etc/apache2/ssl/webservers-CA.pem',
        'ssl_webserver_ca'
        )
    for service in get_all_servicenames():
        write_file_from_option(
            '/etc/apache2/waf/{}.conf'.format(service),
            service + '_overwrite',
            remove_if_empty=True,
            banner=True
            )
        write_file_from_option(
            '/etc/modsecurity/{}/waf.conf'.format(service),
            service + '_securityrules',
            remove_if_empty=True,
            banner=True
            )
        write_file_from_option(
            '/etc/apache2/ssl/{}-cert.pem'.format(service),
            service + '_ssl_cert'
            )
        write_file_from_option(
            '/etc/apache2/ssl/{}-key.pem'.format(service),
            service + '_ssl_key'
            )


# Helper functions

# Get a list of all service names
def get_all_servicenames():
    return map(lambda x: x[:x.rindex('-backend')],
               filter(lambda t: t.endswith('-backend'),
                      relation_types()
                     )
              )


# Take a config field by name and write it into a file
def write_file_from_option(path, option_name, remove_if_empty=False, banner=False):
    config = orig_config_get()
    directory = os.path.dirname(path)
    if not os.path.exists(directory):
        os.makedirs(directory)
    if not data_changed('waf_{}'.format(option_name), config[option_name]):
        log("No changes for {}".format(option_name))
        return
    if not config[option_name] and remove_if_empty:
        log("Not writing {} because {} is empty".format(path, option_name))
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
        return
    log('Writing {}'.format(path))
    with open(path, 'w') as f:
        if banner:
            f.write(juju_banner())
        f.write(str(base64.b64decode(config[option_name]), 'utf-8'))
    set_state('apache.changed')


# FIXME Will not be triggered when port is changed
# Write a vhost file when the backend becomes available
def write_vhost(backend, service):
    config = extract_service_config(service, orig_config_get())
    context = {
        'service': service,
        'use_syslog': orig_config_get()['use_syslog'],
        'hosts': hosts_for_backend(backend)
    }
    context.update(config)
    if not data_changed(service + '.vhost', context):
        log("No changes for {}".format(service))
        return
    render(
        source='proxy_vhost.template',
        target='/etc/apache2/sites-enabled/{}.conf'.format(service),
        owner='root',
        perms=0o644,
        context=context
        )
    set_state('apache.changed')


# Flatten hosts in one list
def hosts_for_backend(backend):
        return reduce(
           lambda x, y: x + y, map(
                lambda srv: srv['hosts'], backend.services()), []),


# Extract config keys prefixed with $service_
# and stripping service name in result
def extract_service_config(service, config):
    result = {}
    for key in filter(lambda k: k.startswith(service + '_'), config.keys()):
        result[re.sub(service + '_', '', key)] = config[key]
    return result


def enable_module(module=None):
    if module is None:
        return True
    if os.path.exists("/etc/apache2/mods-enabled/%s.load" % (module)):
        log("Module already loaded: %s" % module)
        return True
    return_value = subprocess.call(['/usr/sbin/a2enmod', module])
    if return_value != 0:
        return False
    set_state('apache.changed')


def juju_banner():
    return ('''#
#    "             "
#  mmm   m   m   mmm   m   m
#    #   #   #     #   #   #
#    #   #   #     #   #   #
#    #   "mm"#     #   "mm"#
#    #             #
#  ""            ""
# This file is managed by Juju. Do not make local changes.
#
''')
