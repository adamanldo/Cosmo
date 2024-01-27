## Cosmo

A Discord bot written with Discord.py that outputs formatted, color-coordinated images of your currently playing Last.fm song.

![Pulse / Quartet](/examples/stevereich.png)
![Pacific](/examples/haruomi.png)
![Get to Heaven](/examples/everythingeverything.png)

### [Add this bot to my server](https://discord.com/api/oauth2/authorize?client_id=516324491618680832&permissions=35840&scope=bot)

### Usage

Use `.set [username]` to associate your Last.fm username with your Discord account

Use `.fmi` to output your currently playing Last.fm song

Use `.cd` to start a 10 second countdown (for synchronizing listening parties)

### Technical Notes

- Dominant colors are found through [k-means clustering](https://en.wikipedia.org/wiki/K-means_clustering) via the [scikit-learn](https://scikit-learn.org/stable/) package
- Uses the [CIELAB](https://en.wikipedia.org/wiki/CIELAB_color_space) color space for more accurate clustering, as well as the [CIEDE2000 Color-Difference Formula](http://www2.ece.rochester.edu/~gsharma/ciede2000/ciede2000noteCRNA.pdf) to pick a secondary that is perceptually different enough (if one exists)

### Running your own instance

I'd rather you use the "Add this bot to my server" link and use my instance, but if you'd like to run your own you can do it with the instructions below:

1. Make sure you are running Python 3.8 or higher
2. Clone the repository
3. Set up venv with `python3.8 -m venv venv` and activate it with `source venv/bin/activate`
4. Install dependencies with `python3.8 -m pip install -U -r requirements.txt`
5. Create a `.env` file in the base directory with two variables, `API_KEY` and `DISCORD_TOKEN`, where API_KEY contains your Last.fm API key and DISCORD_TOKEN contains your discord bot's private token
6. Using PostgreSQL 10 or higher and using the psql tool, create a database `cosmo` under the default user `postgres`, then create a table called `discord` within it:

```
CREATE DATABASE cosmo;
CREATE TABLE discord ( id bigint PRIMARY KEY UNIQUE, username TEXT NOT NULL );
```
7. Note that the bot is assuming [authentication](https://www.postgresql.org/docs/10/auth-methods.html) is set to "trust"
8. Start the PostgreSQL server with `sudo service postgresql start`
9. Run the bot with `python3.8 launcher.py`

### Known issues and future plans

- There are some issues with font rendering, especially with emojis and certain language fonts that haven't been added yet. I'm working on this now.
- In the future, I'd like to add chart functionality to visualize top played albums over different time periods.