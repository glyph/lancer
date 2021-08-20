# This Project is Now Closed

I wrote `lancer` at a time when:

1. `txacme` was still actively maintained,
2. it [worked with the production version of Let's
   Encrypt](https://github.com/twisted/txacme/issues/151), and
2. using certbot for offline challenges involved hand-manipulating DNS records
   and was really difficult.

Today, none of these things are true any longer.  If you want to provision
certificates for your offline computers, you can use DNS plugins, like [this
one for Gandi](https://github.com/obynio/certbot-plugin-gandi), [this one for
Rackspace](https://github.com/komputerwiz/certbot-dns-rackspace), or [this one
for route53](https://certbot-dns-route53.readthedocs.io/en/stable/).  Getting a
local certificate like the ones `lancer` used to issue is as simple as:

```bash
# make a gandi.ini with your credentials

mkdir -p ~/.certbot/config/live
mkdir -p ~/.certbot/config/config
mkdir -p ~/.certbot/config/work
mkdir -p ~/.certbot/config/logs

certbot \
    --config-dir ~/.certbot/config/ \
    --work-dir ~/.certbot/work/ \
    --logs-dir ~/.certbot/logs/ \
    certonly \
    --domain "${GANDI_HOST}" \
    --authenticator dns-gandi \
    --dns-gandi-credentials ~/Secrets/Gandi/gandi.ini \
    ;
```

Massaging this to work with `txsni` then involves just glomming the `pem` files
together (at least until [`txsni` just does this
directly](https://github.com/glyph/txsni/issues/31)), like so:

```bash
cd ~/.certbot/config/live || exit 1;

mkdir ~/.txsni/

for each in *; do
    if [ -d "${each}" ]; then
        (
            cat "${each}/privkey.pem";
            cat "${each}/fullchain.pem";
        ) > ~/.txsni/"${each}".pem;
    fi;
done;

twist web --listen="txsni:$HOME/.txsni:tcp:8443" --path .
```

Since this project hasn't worked for quite some time, I will archive it; the
original README is left for posterity below.

------

# LAN-Cer: Certificates For Your LAN

`lancer` is a tool which will quickly and simply provision certificates for any
number of hosts in a domain, using Let's Encrypt, assuming that you have an
API-controlled DNS service.

## The Problem

You have too many computers.  Too many (all) of them have to talk to the
Internet.  And, as we all know, any computer on the internet needs a TLS
certificate and the [lock
icon](https://en.wikipedia.org/wiki/Padlock#Padlock_icon_symbolising_a_secure_web_transaction)
that comes with it if you want to be able to talk to it.

For example:

1. Maybe you need to test some web APIs that [don't
   work](https://sites.google.com/a/chromium.org/dev/Home/chromium-security/deprecating-powerful-features-on-insecure-origins)
   without HTTPS, so you need a development certificate for localhost.
2. Maybe you have an [OpenWRT](https://www.openwrt.org/) router and you need to
   administer it via its web interface; you don't want every compromised IoT
   device or bored teenager on your WiFi to be able to read your administrator
   password.

## The Bad Old Days

Previously the way you'd address problems like this would be to:

- ⚠️😡⚠️ use a garbage self-signed root and click through annoying warnings all
  the time
- 🔒️🗑️🔒️ add a garbage self-signed root to your trust store
- 🔥😱🔥 turn off certificate validation entirely in your software

These are all bad in similar ways: they decrease your security and they require
fiddly, machine-specific configuration that has to be repeated on every new
machine that needs to talk to such endpoints.

## The Solution

Let's Encrypt is 99% of the solution here.  And, for public-facing internet
services, it's almost trivially easy to use; many web servers provide built-in
support for it.  But you don't want to use production certificates for your
main website on your development box: you want to put an entry in `/etc/hosts`
under a dedicated test domain name, and you shouldn't have to figure out how to
route inbound public traffic to a web server on that host name in order to
respond to a challenge.

Luckily, Let's Encrypt offers DNS-01 validation, so all you need to do is
update a DNS record.  Lancer uses this challenge.

## What You Need

Your DNS needs to be hosted on a platform that supports `libcloud` (Rackspace
DNS and CloudFlare are two that I have tested with), or Gandi's' V5 API which
Lancer has specific support for.  You will need an API key.

## How To Use It

1. `pip install lancer`
2. `mkdir certificates-for-mydomain.com`
3. Create empty files for the certificates you want to provision: `touch
   certificates-for-mydomain.com/myhost1.lan.mydomain.com.pem
   certificates-for-mydomain.com/myhost2.lan.mydomain.com.pem` .
4. `lancer certificates-for-mydomain.com`

Upon first run, lancer will ask you 4 questions:

1. what driver do you want to use?  this should be the libcloud driver name, or
   'gandi' for the Gandi V5 API.
2. what is your username?
3. what is the DNS zone that you will be provisioning certificates under?
   (usually this is the [registrable part](https://publicsuffix.org/) of the
   domain name; if you want certificates for `lan.somecompany.com` then your
   zone is usually `somecompany.com`)
4. what is your API key?  This will be prompted for and stored with
   [Secretly](https://github.com/glyph/secretly), which uses
   [Keyring](https://github.com/jaraco/keyring) to securely store secrets; this
   may mean that in certain unattended configurations you might need
   [keyrings.alt](https://github.com/jaraco/keyrings.alt) to store your API key
   in a configuration file rather than something like
   [Keychain](https://en.wikipedia.org/wiki/Keychain_(software)) or
   [GnomeKeyring](https://wiki.gnome.org/Projects/GnomeKeyring).

It will store the answers to the first three questions in
`certificates-for-mydomain.com/lancer.json` and the secrets depending upon your
keyring configuration, so you shouldn't need to answer them again (although you
may need to click through a security confirmation on subsequent attempts to
allow access to your API key).

Wait for `lancer` to log that it has successfully provisioned your
certificates, and copy your now-no-longer-empty `.pem` files (which will each
contain a certificate, chain certificates, and a private key) to wherever you
need them on your LAN.  You can kill it with `^C` or you can just leave it
running in the background and let it auto-renew every 90 days or so.

If you don't leave it running, to renew your certificates when they've expired,
simply run `lancer certificates-for-mydomain.com` again, and any expired or
soon-to-expire `.pem` files in that directory will be renewed and replaced.
You can add new certificates at any time by creating new, empty
`fully-qualified-domain-name.pem` files,
