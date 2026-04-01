# TLDR

Going through the SES setup process

## Configure the preliminary SES setup

- Go to: https://us-east-1.console.aws.amazon.com/ses/home?region=us-east-1
- Create an identity: https://us-east-1.console.aws.amazon.com/ses/home?region=us-east-1#/identities/create
  - Identity details: `cmdlabs.io`
  - Verify domain: `DKIM-based domain verification`
- Publish DNS Records to Route 53

## Provision an IAM cred with access to send emails from the cmdlabs.io domain

- Create an IAM user
- CLI interface access key

## Setup a config set

Coming soon!
