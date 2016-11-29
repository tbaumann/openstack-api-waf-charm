from charms.reactive import when, when_not, set_state
from charmhelpers.core.hookenv import (
    open_port,
    close_port,
    log,
    config as orig_config_get,
    relations_of_type,
    relation_set,
    relation_ids,
    unit_get,
    status_set
)
from charmhelpers.core.host import service_restart, service_start, service_stop


@when('apache.start')
@when_not('apache.started')
def start_apache():
    status_set('maintenance', 'Starting Apache')
    assert service_start('apache2'), 'Failed to start Apache2'
    set_state('apache.started')


@when('apache.started')
def started():
    status_set('active', 'Ready')


@when('apache.available')
def setup_apache():
    status_set('maintenance', 'Setting up Apache')
    # prepare apache stuff
    set_state('apache.start')
