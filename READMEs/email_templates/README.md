# TLDR

Some design notes about working with email templates


##

Ultimately, The email templates will be stored in the DB in the `email_templates` table. But here are some useful utilities for developing them a little bit easier.

##

```sh
python -m scripts.download_email_templates
python -m scripts.download_email_templates --account-id 1
python -m scripts.upload_email_template <slug>
python -m scripts.upload_email_template rate-your-experience
```