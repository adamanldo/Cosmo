## Cosmo

A Discord bot that outputs formatted, color-coordinated images of your currently playing Last.fm song.

![Pulse / Quartet](/examples/stevereich.png)
![Pacific](/examples/haruomi.png)
![Get to Heaven](/examples/everythingeverything.png)

### [Add this bot to my server](https://discord.com/api/oauth2/authorize?client_id=516324491618680832&permissions=35840&scope=bot)

### Usage

Use `.set [last.fm username]` to associate your Last.fm username with your Discord account

Use `.fmi` to output your currently playing Last.fm song

Use `.cd` to start a 10 second countdown (for synchronizing listening parties)

### Technical Notes

- Dominant colors are found through [k-means clustering](https://en.wikipedia.org/wiki/K-means_clustering) via the [scikit-learn](https://scikit-learn.org/stable/) package
- Uses the [CIELAB](https://en.wikipedia.org/wiki/CIELAB_color_space) color space for more accurate clustering, as well as the [CIEDE2000 Color-Difference Formula](https://en.wikipedia.org/wiki/Color_difference#CIEDE2000) to pick a secondary color.

### Running your own instance

If you'd like to run your own instance, you can do it with the instructions below:

1. Install uv (https://docs.astral.sh/uv/getting-started/installation/)
2. Clone the repository and change directories into the project's root folder
3. Run `uv sync`
4. Create a `.env` file in the base directory with four variables, `LASTFM_API_KEY`, `DISCORD_TOKEN`, `BOT_DEBUG`, and `BOT_PREFIX`: 
    ```
    LASTFM_API_KEY: Your Last.fm API key
    DISCORD_TOKEN: Your Discord bot's private token
    BOT_DEBUG: (0 or 1) Whether you want errors to print to the console. Set this to 1 if you are running this locally, 0 if you are in a production environment
    BOT_PREFIX: The prefix for the bot commands. If set to "?", "?fmi" will be the command to output an fmi
    ```
5. Using PostgreSQL 10 or higher and using the psql tool, create a database `cosmo` under the default user `postgres`, then create a table called `discord` within it:

```
CREATE DATABASE cosmo;
CREATE TABLE discord ( id bigint PRIMARY KEY UNIQUE, username TEXT NOT NULL );
```
6. Set the Postgres [authentication](https://www.postgresql.org/docs/10/auth-methods.html) method to "trust"
7. Start the PostgreSQL server. On Linux, the command is: `sudo service postgresql start`
8. Run the bot with `uv run launcher.py`

### Known issues

- There are problems with some strange Unicode characters used in a few song names. They are displayed correctly on the image but the function to wrap the text doesn't seem to correctly size them, leading to the text overflowing onto the avatar.
- Font issues should be fixed as of 5/6/2024. We are using imagetext-py, which contains font fallbacks. If there are issues with languages I haven't added yet, please open an issue and I can look into adding them. 
- Arabic and Hebrew should be rendered properly as of 12/15/2024 thanks to some useful Python libraries.
