
import sys, json, six

from secretly import secretly
from functools import partial

from twisted.internet.defer import inlineCallbacks
from twisted.internet.task import react
from twisted.python.filepath import FilePath
from twisted.python.components import proxyForInterface
from twisted.logger import globalLogBeginner, textFileLogObserver

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

from josepy.jwk import JWKRSA
from josepy.jwa import RS256

from txacme.service import AcmeIssuingService
from txacme.store import DirectoryStore
from txacme.client import Client
from txacme.challenges._libcloud import _validation
from txacme.interfaces import IResponder
from txacme.urls import LETSENCRYPT_DIRECTORY, LETSENCRYPT_STAGING_DIRECTORY
from txacme.util import generate_private_key
from txacme.challenges import LibcloudDNSResponder

from ._cloudflare import CloudflareV4Responder
from ._gandi import GandiV5Responder
from ._common import ConsistencyChecker

def maybe_key(pem_path):
    acme_key_file = pem_path.child(u'client.key')
    if acme_key_file.exists():
        key = serialization.load_pem_private_key(
            acme_key_file.getContent(),
            password=None,
            backend=default_backend()
        )
    else:
        key = generate_private_key(u'rsa')
        acme_key_file.setContent(
            key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            )
        )
    acme_key = JWKRSA(key=key)
    return acme_key



class WaitingResponder(proxyForInterface(IResponder, "_original")):

    def __init__(self, original, reactor):
        self._original = original
        self._reactor = reactor


    @inlineCallbacks
    def start_responding(self, server_name, challenge, response):
        validation = _validation(response)
        domain_name = challenge.validation_domain_name(server_name)
        yield super(WaitingResponder, self).start_responding(server_name, challenge, response)
        yield ConsistencyChecker.default(self._reactor).check(domain_name, validation)



def main(reactor):
    acme_path = FilePath(sys.argv[1]).asTextMode()
    myconfig = acme_path.child("lancer.json")
    if myconfig.exists():
        cfg = json.loads(myconfig.getContent().decode("utf-8"))
        driver_name = cfg['driver_name']
        zone_name = cfg['zone_name']
        user_name = cfg['user_name']
        staging = cfg.get('staging', False)
    else:
        driver_name = six.moves.input("driver ('rackspace' or 'cloudflare')? ")
        user_name = six.moves.input("user? ")
        zone_name = six.moves.input("zone? ")
        staging = False
        myconfig.setContent(json.dumps({
            "driver_name": driver_name,
            "user_name": user_name,
            "zone_name": zone_name,
            "staging": staging
        }).encode("utf-8"))

    globalLogBeginner.beginLoggingTo([textFileLogObserver(sys.stdout)])
    def action(secret):
        password = secret
        if driver_name == 'gandi':
            responders = [
                WaitingResponder(
                    GandiV5Responder(api_key=password, zone_name=zone_name),
                    reactor
                )
            ]
        elif driver_name == 'cloudflare':
            responders = [
                CloudflareV4Responder(email=user_name, api_key=password,
                                      zone_name=zone_name)
            ]
        else:
            responders = [
                WaitingResponder(
                    LibcloudDNSResponder.create(
                        reactor, driver_name, user_name, password, zone_name
                    ),
                    reactor
                )
            ]
        acme_key = maybe_key(acme_path)
        cert_store = DirectoryStore(acme_path)
        if staging:
            le_url = LETSENCRYPT_STAGING_DIRECTORY
        else:
            le_url = LETSENCRYPT_DIRECTORY
        client_creator = partial(Client.from_url, reactor=reactor,
                                 url=le_url,
                                 key=acme_key, alg=RS256)
        clock = reactor
        service = AcmeIssuingService(cert_store, client_creator, clock,
                                     responders)
        service._registered = False
        return service._check_certs()
    return secretly(reactor, action=action,
                           system='libcloud/' + driver_name,
                           username=user_name)


def script():
    react(main)
