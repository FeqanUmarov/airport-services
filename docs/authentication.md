# Authentication

## Create the first administrator

Public registration is intentionally disabled. Create the first administrator
from the project directory:

```bash
make create-admin \
  username=admin \
  email=admin@example.com \
  first_name=Admin \
  last_name=User
```

The command asks for the password interactively and requires at least 12
characters. The password is stored as an Argon2 hash.

## Login

`POST /api/v1/auth/login` uses OAuth2 form data, not JSON:

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'username=admin&password=YOUR_PASSWORD'
```

The `username` field accepts either username or email.

## Current user

```bash
curl http://localhost:8000/api/v1/auth/me \
  -H 'Authorization: Bearer ACCESS_TOKEN'
```

## Rotate a refresh token

```bash
curl -X POST http://localhost:8000/api/v1/auth/refresh \
  -H 'Content-Type: application/json' \
  -d '{"refresh_token":"REFRESH_TOKEN"}'
```

Refresh tokens are single-use. A successful refresh revokes the old token and
returns a new access/refresh pair.

## Logout

```bash
curl -X POST http://localhost:8000/api/v1/auth/logout \
  -H 'Content-Type: application/json' \
  -d '{"refresh_token":"REFRESH_TOKEN"}'
```

Logout revokes the supplied refresh token. Existing access tokens remain valid
until their short expiration time is reached.

## Logout from every session

```bash
curl -X POST http://localhost:8000/api/v1/auth/logout-all \
  -H 'Authorization: Bearer ACCESS_TOKEN'
```

This revokes every active refresh token belonging to the authenticated user.
Already issued access tokens remain valid until their short expiration time.

## Change password

```bash
curl -X POST http://localhost:8000/api/v1/auth/change-password \
  -H 'Authorization: Bearer ACCESS_TOKEN' \
  -H 'Content-Type: application/json' \
  -d '{
    "current_password":"CURRENT_PASSWORD",
    "new_password":"NEW_SECURE_PASSWORD"
  }'
```

The new password must contain 12-128 characters and must differ from the
current password. A successful password change revokes all refresh tokens, so
the user must log in again to obtain a new token pair.

## Smoke test

```bash
make auth-smoke
```

The smoke test creates a disposable user, exercises login, `/me`, refresh
rotation and logout, then removes the user and its token records.
