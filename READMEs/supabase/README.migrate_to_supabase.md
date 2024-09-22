# TLDR

Documenting steps of moving Postgres DB from Render.com

## PHASE 1

- 1st created a project called `kalygo3` in the default Org
- Copied the credentials for the DB provisioned in Supabase into this project
- Run all migrations
  - `alembic upgrade head` WORKED √

## PHASE 2

- Backed up Kalygo DB
  - ansible-playbook --inventory inventory.prod --key-file "<PATH_TO_PEM_FILE>" backup_db.yml

## PHASE 3

- Run another Cloud Run service dedicated to Kalygo
  - right now `kalygo-v3` is running the SWARMS PLAYGROUND application
  - rename `kalygo-v3` to be called `swarms-playground`
  - create new project called `kalygo`

