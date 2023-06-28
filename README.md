# GPT-Assistant

Or like a fun bot or something.

This project sets up a GPT-backed chat bot for Discord.  It optionally provides long-term memory functionality (based heavily on [this repo](https://github.com/prestoj/long-term-chat)), as well as some other features, such as multi-tenant bot hosting, that I hope to expand on.

## Setup

Simply, using Python 3.10 (or a similar version), install the requirements:

    pip3 install -r requirements

Create a `.env` file with the following environment variables:

- `DISCORD_BOT_TOKEN`: The bot token [supplied by Discord after creating a bot account](https://discordpy.readthedocs.io/en/stable/discord.html).
- `OPEN_API_KEY`: The API key [provided by OpenAI with access to GPT](https://platform.openai.com/docs/introduction).
- `DB_URI`: The URI to a PostgreSQL database.
- `DISCORD_USERS`: A list of "raw" Discord usernames who have poweruser access (i.e., can run "dangerous" commands).

With that file populated in the root directory of this project, you can start the bot locally with:

    python3 src/main.py

Once running, you have to configure a bot using the `>set config <bot name>` command. You can solicit a response from the bot (after it's been invited to a server) by either mentioning it or responding to one of it's messages.

## Docker

You can build this app with the supplied Dockerfile, or use the [image hosted on Docker Hub](https://hub.docker.com/repository/docker/nathanmargaglio/assistant/general).  This is also a good way to [host the Postgres database](https://hub.docker.com/_/postgres).

## Hosting

You should be able to host this anywhere you can deploy your container and connect to a Postgres database.  I currently host it using [AWS Lightsail](https://aws.amazon.com/lightsail/), which seems as easy as it gets to set something like this up.

I'm currently running the container out of a Micro node ($10 per month, with 3 months free trial) and I'm having Lightsail host the database for me ($15 per month, with 3 months free).  You could probably use a smaller container and even host the database yourself if you want things to be cheaper, and, of course, you could also just run all of this locally or in some other infrastructure.  The app doesn't (currently) require inbound traffic, so no need to fuss with networking _too_ much.

## TO-DO

- Make the Postgres database an optional feature.
- Use [function calling](https://platform.openai.com/docs/guides/gpt/function-calling) more intricately (e.g., call social media APIs, manage calendars, etc.)
- Have the bot run asynchronously, i.e., it can message the server without being messaged first.