# TLDR

Going through the SES config set setup process

## Set up a config set

- Create a config set
- Enable reputation metrics
- Configure the identity
  - Link the config set with the relevant identity

## Add an event destination to the config set

- Find the event destination tab on the 
  - STEP 1: Select all events
  - STEP 2: Specify the `Amazon SNS` destination option
  - STEP 3: Create an SNS topic
    - call it `cmdlabs_config_set_sns`
    - Add a subscription to the topic
      - Protocol: `HTTPS` 
      - Use an n8n endpoint for testing
      - Need to confirm the subscription before the events flow
        - Request confirmation
        - Confirm subscription
          - Use the `SubscribeURL` to confirm the subscription
      - Attach the subscription to the topic  
  - STEP 4: Add another topic to subscribe for "production" events
  - STEP 5: Send test email and watch the events flow
      - Note that HTML emails are required for tracking `open` and `click` events
