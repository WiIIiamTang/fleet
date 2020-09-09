# Fleet

A bandori data viewer for discord. It uses the bandori.party API (and bandori database API for songs). English names for cards may not be accurate. See the [pydori api](https://github.com/WiIIiamTang/pydori).

![example](https://i.imgur.com/QDWqoUW.png)

# Info

This discord bot grabs data from the bandori.party and bandori database public apis. It formats the info into readable discord embeds. Features include interactable card embeds, browsing through lists of bandori cards, members, and songs, and a fully functional music bot.


This bot uses the pydori module to get info from the apis, so you can use certain filters.


To get started, 

1. install all the requirements and host the bot somewhere.
2. Create a folder called 'data' and run main.py.
3. Update the database by running rebuild command.


## Features
- **Check and update current ongoing event, and send it to a channel. Can be set to update automatically every few hours.**

- **Check and update active gachas, and send it to a channel. Can be set to update automatically every few hours.**

- **Card, Member, and Song querying with additional optional filters.**



## Bot usage
See below for different commands accepted by the bot. Each entry has:
 - Command
 - Description
 - Additional Info

___
#### Cards
```
;card [--id] [--trained] [--rarity] [--attr] [--skilltype] [--member]
;cardname [[str]]
```
Query card with optional filters, where
- *id* is followed by an int
- *trained* is a flag
- *rarity* is followed by an int from 2-4
- *attr* is followed by an str (valid ones: Pure, Power, Cool, Happy)
- *skilltype* is followed by an int *See skilltypes below
- *member* is followed by an int

Pass a valid string to *cardname* to get the card (must match exactly, capitals not considered)
```
skilltypes = {
        0 : 'Score up',
        1 : 'Life recovery',
        2 : 'Perfect lock',
        3 : 'Life guard'
    }
```

#### Members
```
;member [--id] [--year]
;membername [[str]]
```
Query member data with optional filters, where
- *id* is followed by an int
- *year* is followed by a string indicating the school year (valid: First, Second, Third)

Pass a valid string to *membername* to get the member (must match exactly, capitals not considered)
```
;song [--id] [--band]
;songname [[str]]
```
Query song data with optional filters, where
- *id* is followed by an int
- *band* is followed by an int *See bands below

Pass a valid string to *songname* to get the song (must match exactly, capitals not considered)
```
 bands = {
        1 : 'Poppin\'Party',
        2 : 'Afterglow',
        3 : 'Hello, Happy World!',
        4 : 'Pastel＊Palettes',
        5 : 'Roselia',
        6 : 'Glitter*Green',
        7 : 'Kasumi x Afterglow',
        8 : 'Poppin\'Party x Glitter*Green',
        9 : 'Kasumi Toyama',
        10 : 'Tae Hanazono',
        11 : 'Rimi Ushigome',
        12 : 'Saya Yamabuki',
        13 : 'Arisa Ichigaya',
        14 : 'GBP! Special Band',
        15 : 'Hello, Happy World! × Ran × Aya',
        16 : 'Kasumi×Ran×Aya×Yukina×Kokoro',
        17 : 'Aya×Moca×Lisa×Kanon×Tsugumi',
        18 : 'RAISE A SUILEN',
        19 : 'Roselia × Ran',
        20 : 'Poppin\'Party × Aya × Kokoro'
    }
```
#### Music
```
;play [[int] | [str]]
;pause
;skip
;queue | ;q
;stop
;leave
```
Music player: plays the bandori song with the passed id, or the youtube url if that is given instead. Bandori songs are game-sized in length.


```
;eventnow
```
Displays the current ongoing event.


```
;gachanow
```
Displays all active gachas.

