# pyhatchery
App store for SHA2017 badge derivatives (such as Disobey19)

## Quick start
1. Create new virtualenv (`python3 -m virtualenv venv` or something similar) and activate it
2. Install dependencies: `pip install -r requirements.txt`
3. Change config values inside `app.py`
4. Initialize database: `sqlite3 data.db ".read base.sql"`
5. Add a test user by using SQLite CLI (because for now user management is nonexistent): `INSERT INTO user (name, email, password) VALUES ("admin", "admin@localhost", "$2b$12$4uDb/pAIcNLahGg.FwV7EOki5WhX35zYFTnlv6nsFiOG5DWHXeAAq");` (user admin, password admin)
6. Run: `./app.py`

## Notes
* You can't edit anything yet. Only creating and viewing apps and releases are supported as of now (2019-01-20).
* If you want to use this with SSL, create a self-signed certificate (Google it) as a PEM file. See `app.py` SSL_CERT_PATH.
* Deploying isn't supported. There are no releases. This has been hacked together in a day or two.
