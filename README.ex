# Overview

Web Application Firewall (WAF) for openstack http API and services.

Based on Apache_Mod_Security.

# Usage


Step by step instructions on using the charm:

juju deploy servicename


Then add the relations which are required.
All inactive relations will not run and don't need to be configured.
A relation that is configured will need to be fully configured before that is done. (SSL settings)

juju add-relation service-backend service


## Scale out Usage

This charm can be scaled if a load balancer is placed in front of it.

The backends can be scaled too. The proxy endpoints will be added as required.

## Known Limitations and Issues

Changes on port numbers will not be correctly handled after a relation was sucessfully set up.
The relation will need to re-enabled or changed to make the change stick.

# Configuration

There are two global options:

* securityrules (Base64)
* ssl_webserver_ca (Base64)

Every service has a set of config options prefixed with the service name.
They should have sensible defaults. But can be changed.

* service_backend_proto Protocol to use towards the backend. http or https
* service_location Path which will be passed through for this service
* service_overwrite Optional apache config snipped included in the VHost context (Base64)
* service_port Portnumer. The same for frontend and backend
* service_securityrules Apache include for the service specific security rules (Base64)
* service_ssl_cert Base64 encoded certificate for the frontend
* service_ssl_key Base64 encoded ssl key for the frontend

# Contact Information FIXME

Though this will be listed in the charm store itself don't assume a user will
know that, so include that information here:

## Upstream Project Name

  - Upstream website
  - Upstream bug tracker
  - Upstream mailing list or contact information
  - Feel free to add things if it's useful for users


[service]: http://example.com
[icon guidelines]: https://jujucharms.com/docs/stable/authors-charm-icon
