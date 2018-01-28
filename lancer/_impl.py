
import sys, json, six

from secretly import secretly
from functools import partial

from twisted.internet.defer import Deferred
from twisted.internet.task import react
from twisted.python.filepath import FilePath
from twisted.logger import globalLogBeginner, textFileLogObserver

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

from josepy.jwk import JWKRSA
from josepy.jwa import RS256

from txacme.service import AcmeIssuingService
from txacme.store import DirectoryStore
from txacme.client import Client
from txacme.urls import LETSENCRYPT_DIRECTORY, LETSENCRYPT_STAGING_DIRECTORY
from txacme.util import generate_private_key
from txacme.challenges import LibcloudDNSResponder

from ._gandi import GandiV5Responder

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


def main(reactor):
    acme_path = FilePath(sys.argv[1]).asTextMode()
    myconfig = acme_path.child("lancer.json")
    if myconfig.exists():
        cfg = json.loads(myconfig.getContent())
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
                GandiV5Responder(api_key=password, zone_name=zone_name)
            ]
        else:
            responders = [
                LibcloudDNSResponder.create(reactor, driver_name,
                                            user_name, password, zone_name)
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
        service.startService()
        forever = Deferred()
        return forever
    return secretly(reactor, action=action,
                           system='libcloud/' + driver_name,
                           username=user_name)


def script():
    react(main)
