# Supabase database trust anchor

`supabase-root-ca.crt` is a public CA certificate, not a private key or credential.
It was downloaded over HTTPS from the production certificate URL used by the
[Supabase Studio source](https://github.com/supabase/supabase/blob/master/apps/studio/hooks/custom-content/custom-content.json):

https://supabase-downloads.s3-ap-southeast-1.amazonaws.com/prod/ssl/prod-ca-2021.crt

Certificate SHA-256:
`807025ad50d4ed219d2c9c7d299c004f824eb00cf7f65afef607d07b72e6cafa`

Use `sslmode=verify-full` in `DATABASE_URL` and set
`DATABASE_SSL_ROOT_CERT=deploy/supabase-root-ca.crt`. Settings resolve this path
from the application directory. Actual session and transaction pooler connections
passed authentication and certificate/hostname verification with this certificate.
Review the provider's certificate changes and expiry during upgrades; do not
silently weaken verification if a future connection fails.
