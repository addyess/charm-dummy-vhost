#!/usr/bin/env python3

import base64
import logging
import sys

sys.path.append('lib') # noqa

from ops.charm import CharmBase, CharmEvents
from ops.framework import (
    EventSource,
    EventBase,
    StoredState,
)

from ops.model import ActiveStatus
from ops.main import main
from pathlib import Path

logger = logging.getLogger(__name__)


class DummyVhostReadyEvent(EventBase):
    pass


class DummyVhostCharmEvents(CharmEvents):
    vhost_ready = EventSource(DummyVhostReadyEvent)


class Charm(CharmBase):

    on = DummyVhostCharmEvents()

    document_root = Path('/var/www/dummy-vhost')
    index_file = document_root / 'index.html'
    index_template = 'templates/index.html'
    vhost_template = 'templates/dummy-vhost.conf'

    VHOST_PORT = 80

    state = StoredState()

    def __init__(self, *args):
        super().__init__(*args)

        try:
            self.state.ready
        except AttributeError:
            self.state.ready = False

        self.framework.observe(self.on.install, self)
        self.framework.observe(self.on.stop, self)

        self.framework.observe(self.on.vhost_config_relation_joined, self)
        self.framework.observe(self.on.vhost_ready, self)

    def on_install(self, event):
        logger.info(f'on_install: Setting up dummy vhost files.')

        self.document_root.mkdir()

        with open(self.framework.charm_dir / self.index_template) as f:
            index_content = f.read()
        with open(self.index_file, 'w') as f:
            f.write(index_content)

        self.state.ready = True
        self.on.vhost_ready.emit()

    def on_stop(self, event):
        logger.info(f'on_stop: removing dummy vhost files.')
        self.document_root.rmdir()

        self.state.ready = False

    def on_vhost_ready(self, event):
        self.framework.model.unit.status = ActiveStatus()

    def on_vhost_config_relation_joined(self, event):
        if not self.state.ready:
            event.defer()
            return

        if self.unit.is_leader():
            with open(self.framework.charm_dir / self.vhost_template, 'rb') as f:
                vhost_content = base64.b64encode(f.read()).decode('utf-8')
            vhost_rdata = '- {' f'port: "{self.VHOST_PORT}", template: {vhost_content}' '}'
            event.relation.data[self.app]['vhosts'] = vhost_rdata
            event.relation.data[self.unit]['vhosts'] = vhost_rdata
        else:
            for k in event.relation.data[self.unit].keys():
                del event.relation.data[self.unit][k]


if __name__ == '__main__':
    main(Charm)
