import attr
import treq

from txacme.interfaces import IResponder
from txacme.challenges._libcloud import _validation
from zope.interface import implementer
from twisted.internet.defer import inlineCallbacks
from twisted.internet.task import deferLater

from hyperlink import parse

base = parse("https://api.cloudflare.com/client/v4/")

def global_reactor():
    from twisted.internet import reactor
    return reactor

@attr.s(hash=False)
@implementer(IResponder)
class CloudflareV4Responder(object):
    """
    Cloudflare API V4 responder.
    """
    _email = attr.ib()
    _api_key = attr.ib()
    _zone_name = attr.ib()
    _settle_delay = attr.ib(default=60.0)
    _reactor = attr.ib(default=attr.Factory(global_reactor))

    challenge_type = u'dns-01'

    def _headers(self):
        """
        Auth headers that Cloudflare expects.
        """
        return {
            b"X-Auth-Key": self._api_key,
            b"X-Auth-Email": self._email
        }


    @inlineCallbacks
    def start_responding(self, server_name, challenge, response):
        validation = _validation(response)
        full_name = challenge.validation_domain_name(server_name)
        # subdomain = _split_zone(full_name, self._zone_name)
        zones_list_url = str(base.child("zones").set("name", self._zone_name))

        response = yield treq.get(zones_list_url,
                                  headers=self._headers())
        data = yield response.json()
        assert len(data['result']) == 1
        zone_id = data['result'][0]['id']
        records_base = base.child("zones").child(zone_id).child("dns_records")
        records_query_url = str(records_base
                                .set("type", "TXT")
                                .set("name", full_name))
        response = yield treq.get(records_query_url, headers=self._headers())
        data = yield response.json()
        records = data['result']
        dns_record = {
            "type": "TXT",
            "ttl": 120,
            "name": full_name,
            "content": validation
        }
        if records:
            put_to = str(records_base.child(records[0]["id"]))
            response = yield treq.put(
                put_to, json=dns_record,
                headers=self._headers()
            )
        else:
            post_to = str(records_base)
            response = yield treq.post(post_to, json=dns_record, headers=self._headers())
        yield response.json()
        yield deferLater(self._reactor, self._settle_delay, lambda: None)


    @inlineCallbacks
    def stop_responding(self, server_name, challenge, response):
        # Ignore stop_responding right now.
        yield deferLater(self._reactor, self._settle_delay, lambda: None)
