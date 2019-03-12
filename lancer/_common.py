
import attr

from twisted.names.client import Resolver
from twisted.logger import Logger
from twisted.internet.defer import inlineCallbacks, gatherResults, returnValue
from twisted.internet.task import deferLater

log = Logger("lancer.consistency")

INTERQUERY_DELAY = 5.0


@attr.s
class ConsistencyChecker(object):
    """
    Check the consistency of DNS resolution results.
    """

    _resolvers = attr.ib()
    _reactor = attr.ib()

    @classmethod
    def default(cls, reactor):
        """
        Create a consistency checker with resolvers from Google, Cloudflare,
        OpenDNS, and Level3.
        """
        return cls(
            [
                Resolver(servers=[(addr, 53)], reactor=reactor)
                for addr in [
                    # Google
                    "8.8.8.8",
                    "8.8.4.4",
                    # Level3
                    "4.2.2.2",
                    "4.2.2.1",
                    # OpenDNS
                    "208.67.222.222",
                    "208.67.220.220",
                    # Cloudflare
                    "1.1.1.1",
                    "1.0.0.1",
                ]
            ],
            reactor,
        )

    @inlineCallbacks
    def check(self, name, content):
        """
        Check DNS consistency between a challenge TXT record name and the
        observable response in the DNS.
        """
        while True:
            gathered = yield gatherResults(
                [
                    resolver.lookupText(name).addCallbacks(
                        lambda response: response[0][0].payload.data[0].decode("ascii"),
                        lambda failure: "<nothing>",
                    )
                    for resolver in self._resolvers
                ]
            )
            if gathered and all((each == content) for each in gathered):
                log.info(
                    "all resolvers confirm {name} is {content!r}",
                    name=name,
                    content=content,
                )
                yield deferLater(self._reactor, INTERQUERY_DELAY, lambda: None)
                returnValue(True)
            else:
                log.warn(
                    "expected {content} for {name}: dissenting responses {dissenting}",
                    dissenting=[each for each in gathered if each != content],
                    content=content,
                    name=name,
                )
                yield deferLater(self._reactor, INTERQUERY_DELAY, lambda: None)
