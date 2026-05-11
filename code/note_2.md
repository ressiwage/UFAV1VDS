Client                  Gateway                 Redis               Auth API / Replica
  │                        │                      │                       │
  │ POST /login            │──────────────────────────────────────────>   │
  │ <── access_token ──────│                      │                       │
  │                        │                      │                       │
  │ GET /upload/token      │                      │                       │
  │   Bearer: <token>  ──> │                      │                       │
  │                        │── GET /user ──────────────────────────────>  │
  │                        │ <── {id, username} ───────────────────────── │
  │                        │── SETEX otp:upload:<otp> 60s ──────────> │   │
  │ <── {upload_token} ────│                      │                       │
  │                        │                      │                       │
  │ GET /upload            │                      │                       │
  │   ?upload_token=<otp>  │── GETDEL otp:... ──> │                       │
  │                        │ <── payload ──────── │                       │
  │ <── {url: replica} ────│                      │                       │

схема токенов в upload



ваниль: 283495.60 ms
опт: 165952.60 