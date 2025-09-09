## Refresh Tor DA V3 Authority Keys

1. Generate new authority identity key (should only need to do this once)

From `tor/tor-keys/` directory:

```
tor-gencert --create-identity-key -i authority_identity_key
```

The PEM passphrase used is `warnet`

2. Generate new certificates (expires in 24 months)

```
tor-gencert -i authority_identity_key -s authority_signing_key -c authority_certificate -m 24
```

3. Configure tor

Copy the `fingerprint` value from line 2 in `authority_certificate` and paste in to the top of `tor-entrypoint.sh` as `V3IDENT`


## Build and upload Warnet images

From repository root:

```
./resources/images/tor/build-tor.sh
```