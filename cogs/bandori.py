import discord
import logging
import json
import asyncio
import argparse
import aiohttp
import sys
import os
import io
import shutil
import _pickle as pickle
import youtube_dl
from pydori import bandori_api
from discord.ext import tasks, commands
from discord.utils import get
from discord.voice_client import VoiceClient
from concurrent.futures import ThreadPoolExecutor


logging.basicConfig(level = logging.WARNING, 
                    format = '%(asctime)s - [%(levelname)s] %(message)s',
                    datefmt = '%Y-%m-%d %H:%M:%S')


class ArgumentParser(argparse.ArgumentParser):

    def error(self, message):
        logging.debug(f'Error while parsing arguments: {message}')
        #self.print_help(sys.stderr)
        #self.exit(2, '%s: error: %s\n' % (self.prog, message))

class BandoriViewer(commands.Cog):
    '''
    Bandori data viewer using pydori
    Displays and formats data from the bandori.party api

    English names of cards are inaccurate.
    Availability of songs, cards, items depend on region.
    Resolutions of card art images are smaller when using the api.

    Bandori.party api: data not sorted by region.
    '''

    DB_PATH = 'data/'

    rarity_colors = {
        2 : 0x0f7d6e,
        3 : 0x26d11d,
        4 : 0xeff21d
    }

    skilltypes = {
        0 : 'Score up',
        1 : 'Life recovery',
        2 : 'Perfect lock',
        3 : 'Life guard'
    }

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

    def __init__(self, bot):
        self.bot = bot
        self.bapi = bandori_api()
        self.bapi2 = bandori_api(party=False)
        self.db = {}
        self.loop_state = False
        self.queue = {}

        ########## Load db

        database_exists = os.path.isfile(self.DB_PATH + 'database.pickle')

        if not database_exists:
            logging.critical('There was no database file found. Commands may not work properly.\
Run rebuild to create it as soon as possible.')

        else:
            logging.info(f'Loading database from {self.DB_PATH}')

            with open(self.DB_PATH + 'database.pickle', 'rb') as handle:
                self.db = pickle.load(handle)
        
        
        ########## Argparse

        self.parser = ArgumentParser(description='Bandori arg parser')

        self.parser.add_argument('--id', type=int, help='id for bandori object')


        ###############################################################################
        # Card filter arguments
        self.parser.add_argument('--trained', action='store_true', help='show a trained card or not')

        self.parser.add_argument('--rarity', type=int, help='rarity of card')

        self.parser.add_argument('--attr', type=str, help='attribute of card')

        self.parser.add_argument('--skilltype', type=int, help='skill type of card')

        self.parser.add_argument('--member', type=int, help='member id for the card')

        ###############################################################################
        # Member filter arguments

        self.parser.add_argument('--year', type=str, help='School year of member')

        ###############################################################################
        # Song filter arguments

        self.parser.add_argument('--band', type=int, help='Band that plays the song')
    


    ##### Helper functions for formatting embeds.
    
    def react_check(self, message=None, author=None):
        message = message.id
        def check(reaction, user):
            if user.bot:
                return False
            if reaction.message.id != message:
                return False
            if author != user:
                return False
            return True
        
        return check


    def filter(self, bandori, filters={}):
        if not filter:
            return True
        
        for key, value in filters.items():
            if value is not None:
                if bandori.data[key] != value:
                    
                    return False

        return True
    

    async def send_and_wait_page_selector(self, ctx, emojis=['▶️', '◀️', '❌'], embed=discord.Embed(title='None'), filters ={}, func = None, page=0, db_name=""):
        
        message = await ctx.channel.send(embed=embed)
        check = self.react_check(message=message, author = ctx.author)

        await message.add_reaction(emoji='◀️')
        await message.add_reaction(emoji='▶️')
        await message.add_reaction(emoji='❌')

        while True:
            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=20, check=check)
                
                if str(reaction.emoji) == emojis[0]:
                    
                    await reaction.remove(user)
                    
                    page, new_embed = func(self.db[db_name], page=page+1, filters=filters)

                    await message.edit(embed=new_embed)
                elif str(reaction.emoji) == emojis[1]:
                    
                    
                    await reaction.remove(user)
                    
                    page, new_embed = func(self.db[db_name], page=page-1, filters=filters)

                    await message.edit(embed=new_embed)
                elif str(reaction.emoji) == emojis[2]:
                    break
                
            except Exception as e:
                print('Timeout.')
                print(e)
                break
    
    def page_logic(self, page, data, filters):
        if page < 0:
                page = 0
            
            #print(len(data))

        new_data = []

        for obj in data:
            if self.filter(obj, filters):
                new_data.append(obj)
        
        #print(len(new_data))
        len_cards = len(new_data)
        card_page_amount = 10 # 10 cards per page, 0 - 9

        total_pages = (len_cards // card_page_amount)
        if len_cards % 10 == 0:
            total_pages -= 1
        

        if page > total_pages:
            page = total_pages

        start = card_page_amount * page
        end = start + card_page_amount + 1

        if end >= len_cards:
            end = len_cards
        

        return page, total_pages, new_data, start, end

    
    
    ###### Commands and main formatting functions.

    @commands.command(name = 'rebuild')
    @commands.has_permissions(administrator = True)
    async def rebuild(self, ctx):
        await ctx.channel.send('Warning : you\'re about to rebuild the entire bandori database. Continue? [Y/n]')
        try:
            response = await self.bot.wait_for('message', timeout = 5.0, check = lambda message : message.author == ctx.author)
        except:
            await ctx.channel.send('Timed out, nothing was changed.')
        
        if response.content.lower() == 'y':
            await ctx.channel.send('I\'m updating my database, please don\'t do anything while I save...')
            logging.warning('The database has started updating.')

            loop = asyncio.get_event_loop()
            job_result = await loop.run_in_executor(executor=None, func=self.update_data)
            
            if job_result:
                await ctx.channel.send('Ok! I\'m done updating.')
                logging.warning(f'Successfully updated database at {BandoriViewer.DB_PATH}. Restart the cog!')
            else:
                logging.error('There was an error. The database did not update correctly.')
    

    def update_data(self):
        try:
            self.db['cards'] = self.bapi.get_cards()
            print('Done cards')
            self.db['members'] = self.bapi.get_members()
            print('Done members')
            self.db['events'] = self.bapi.get_events()
            print('Done events')
            self.db['costumes'] = self.bapi.get_costumes()
            print('Done costumes')
            self.db['items'] = self.bapi.get_items()
            print('Done items')
            self.db['areaitems'] = self.bapi.get_areaitems()
            print('Done areaitems')
            self.db['assets'] = self.bapi.get_assets()
            print('Done assets')
            self.db['songs'] = self.bapi2.get_songs()
            print('Done songs')

            with open(self.DB_PATH + 'database.pickle', 'wb') as handle:
                pickle.dump(self.db, handle, protocol=4)

            return True

        except Exception as e:
            logging.error('Error while updating.', exc_info=True)
            return False
    

    # card commands.

    @commands.command(name = 'card')
    async def card(self, ctx, *, message = None):
        
        if message is not None:
            args = self.parser.parse_args(message.split(' '))

            # Get arguments
            #print(args.id)
            id = args.id
            trained = args.trained
            rarity = args.rarity
            attribute = args.attr
            if attribute:
                attribute = attribute[0].upper() + attribute[1:]
            skilltype = BandoriViewer.skilltypes.get(args.skilltype)
            memberid = args.member
            

            filters = {
                    'i_rarity' : rarity,
                    'i_attribute' : attribute,
                    'i_skill_type' : skilltype,
                    'member' : memberid
                }
            
            # if an id arg exists, get the card.
            if id:
                for card in self.db["cards"]:
                    if card.id == id:
                        await ctx.channel.trigger_typing()
                        await self.card_switcher(ctx, embed=self.format_card(card.data, trained), trained=trained, card=card)
                        return
            

            # otherwise we filter.
            elif sum([0 if _ is None else 1 for _ in list(filters.values())]) != 0:
                await ctx.channel.trigger_typing()
                page, embed = self.format_all_cards_embed(self.db["cards"], page=0, filters=filters)
                await self.send_and_wait_page_selector(ctx, embed=embed, filters=filters, func=self.format_all_cards_embed, db_name='cards')

            else:
                await ctx.channel.send('Nothing matched those arguments.')
        
        else:
            
            page, embed = self.format_all_cards_embed(self.db["cards"], page=0)
            await self.send_and_wait_page_selector(ctx, embed=embed, func=self.format_all_cards_embed, db_name='cards')


    @commands.command(name = 'cardname')
    async def cardname(self, ctx, *, message =None):
        for card in self.db["cards"]:
            if card.name is not None:
                if card.name.lower() == message.lower():
                    await ctx.channel.trigger_typing()
                    await self.card_switcher(ctx, embed=self.format_card(card.data), card=card)
                    return
        
        await ctx.channel.send('Did not find a card with that name.')
    


    async def card_switcher(self, ctx, emojis=['🔄', '❌'], embed=discord.Embed(title='None'), trained=False, card=None):
        m = await ctx.channel.send(embed=embed)
        check = self.react_check(message=m, author = ctx.author)

        await m.add_reaction(emoji='🔄')
        await m.add_reaction(emoji='❌')

        while True:
            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=10, check=check)

                if str(reaction.emoji) == emojis[0]:
                    await reaction.remove(user)

                    trained = not trained

                    new_embed = self.format_card(card.data, trained)
                    await m.edit(embed=new_embed)

                    
                elif str(reaction.emoji) == emojis[2]:
                    break
            except:
                print('Timeout.')
                break

    

    def format_card(self, data, trained = False):
        name = ''
        japanese_name = ''
        skill_name = ''
        japanese_skill_name = ''
        rarity = ''.join([':star:' for _ in range(data["i_rarity"])])

        if data["name"] is not None:
            name = data["name"]
        if data["japanese_name"] is not None:
            japanese_name = data["japanese_name"]
        if data["skill_name"] is not None:
            skill_name = data["skill_name"]
        if data["japanese_skill_name"] is not None:
            japanese_skill_name = data["japanese_skill_name"]
        
        embed = discord.Embed(title = name + ' | ' + japanese_name, color=BandoriViewer.rarity_colors[data["i_rarity"]])

        if trained and data["i_rarity"] > 2:
            embed.set_image(url=data["art_trained"])
            embed.set_thumbnail(url=data["image_trained"])
            
        else:
            embed.set_image(url=data["art"])
            embed.set_thumbnail(url=data["image"])
        
        embed.add_field(name = 'Rarity', value=rarity)
        embed.add_field(name = 'Attribute', value=data["i_attribute"])
        embed.add_field(name = 'Info', value=f'Id: {data["id"]}\nMember: [{data["member"]}] {self.bapi.get_members(id=[data["member"]])[0].name}', inline=False)
        embed.add_field(name = 'Stats ([min] - [max])', value=f'```PERF: {data["performance_min"]}\t\t{data["performance_max"]}\nTECH: {data["technique_min"]}\t\t{data["technique_max"]}\nVISL: {data["visual_min"]}\t\t{data["visual_max"]}```',
        inline=False)
        
        embed.add_field(name = 'Skill', value=f'**{skill_name} | {japanese_skill_name}** \n_[Type: {data["i_skill_type"]}]_\
        \n\n(Max Rank) {data["full_skill"]}', inline=False)
        embed.add_field(name = 'Misc', value=f'Cameo: {data["cameo_members"]}\
        \nPromo: {data["is_promo"]}\nOriginal: {data["is_original"]}', inline=False)

        embed.set_footer(text=f'Release date: {data["release_date"]}')

        return embed


    def format_all_cards_embed(self, data, page = 0, filters={}):
        page, total_pages, new_data, start, end = self.page_logic(data=data, page=page, filters=filters)

        cards_page = [card for card in new_data[ start : end ]]

        embed = discord.Embed(title='Bandori Cards')

        for c in cards_page:
            name = ''
            japanese_name = ''
            rarity = ''.join([':star:' for _ in range(c.rarity)])

            if c.name is not None:
                name = c.name
            if c.japanese_name is not None:
                japanese_name = c.japanese_name

            embed.add_field(name=c.id, value=f'{name} | {japanese_name} [{rarity}]', inline=False)
        
        embed.set_footer(text=f'Page {page} of {total_pages}')

        return page, embed

    
    #### Member Command

    
    @commands.command(name='member')
    async def member(self, ctx, *, message=None):
        if message is not None:
            args = self.parser.parse_args(message.split(' '))

            # Get arguments
            #print(args.id)
            id = args.id
            year = args.year
            if year:
                year = year[0].upper() + year[1:]


            filters = {
                'i_school_year' : year
            }
            # if an id arg exists, get the card.
            if id:
                for member in self.db["members"]:
                    if member.id == id:
                        await ctx.channel.trigger_typing()
                        embed = self.format_member(member.data)
                        await ctx.channel.send(embed=embed)
                        return
            
            elif sum([0 if _ is None else 1 for _ in list(filters.values())]) != 0:
                page, embed = self.format_all_members_embed(self.db["members"], page=0, filters=filters)
                await self.send_and_wait_page_selector(ctx, embed=embed, func=self.format_all_members_embed, page=page, db_name='members')
            else:
                await ctx.channel.send('Nothing matched those arguments.')
        
        else:
            page, embed = self.format_all_members_embed(self.db["members"], page=0)
            await self.send_and_wait_page_selector(ctx, embed=embed, func=self.format_all_members_embed, page=page, db_name='members')
    
    @commands.command(name = 'membername')
    async def membername(self, ctx, *, message =None):
        for member in self.db["members"]:
            if member.name is not None:
                if member.name.lower() == message.lower():
                    await ctx.channel.send(embed=self.format_member(member.data))
                    return
        
        await ctx.channel.send('Did not find a card with that name.')



    def format_member(self, data):
        name = ''
        japanese_name = ''
        
        if data["name"] is not None:
            name = data["name"]
        if data["japanese_name"] is not None:
            japanese_name = data["japanese_name"]
        
        
        embed = discord.Embed(title = name + ' | ' + japanese_name)

        embed.set_image(url=data["image"])
        embed.set_thumbnail(url=data["square_image"])
        
        embed.add_field(name = 'Band', value=data["i_band"])
        embed.add_field(name = 'School', value=f'{data["school"]}, {data["i_school_year"]}')
        embed.add_field(name = 'CV', value=f'{data["romaji_CV"]} [{data["CV"]}]')
        
        embed.add_field(name = 'Birthday', value=data["birthday"])
        embed.add_field(name = 'Food Likes', value=data["food_like"])
        embed.add_field(name = 'Food Dislikes', value=data["food_dislike"])
        embed.add_field(name = 'Astrological Sign', value=data["i_astrological_sign"])
        embed.add_field(name = 'Instrument', value=data["instrument"])
        embed.add_field(name = '**Description**', value=data["description"], inline=False)

        embed.set_footer(text=f'Member Id: {data["id"]}')

        return embed
    

    def format_all_members_embed(self, data, page = 0, filters={}):
        page, total_pages, new_data, start, end = self.page_logic(data=data, page=page, filters=filters)

        

        members_page = [member for member in new_data[start:end]]

        embed = discord.Embed(title='Bandori Members')

        for m in members_page:
            embed.add_field(name=m.id, value=f'{m.name} | {m.japanese_name}, {m.instrument}', inline=False)
        
        embed.set_footer(text=f'Page {page} of {total_pages}')

        return page, embed
    

    #### Song Command

    @commands.command(name='song')
    async def song(self, ctx, *, message=None):
        if message is not None:
            args = self.parser.parse_args(message.split(' '))

            # Get arguments
            #print(args.id)
            id = args.id
            band = args.band
            
            filters = {
                'bandId' : band
            }

            # if an id arg exists, get the card.
            if id:
                for song in self.db["songs"]:
                    if song.id == id:
                        await ctx.channel.trigger_typing()
                        embed = self.format_song(song)
                        await ctx.channel.send(embed=embed)

                        return

            elif sum([0 if _ is None else 1 for _ in list(filters.values())]) != 0:
                await ctx.channel.trigger_typing()
                page, embed = self.format_all_songs_embed(self.db["songs"], page=0, filters=filters)
                await self.send_and_wait_page_selector(ctx, embed=embed, filters=filters, func=self.format_all_songs_embed, db_name='songs')

            else:
                await ctx.channel.send('Nothing matched those arguments.')
        
        else:
            page, embed = self.format_all_songs_embed(self.db["songs"], page=0)
            await self.send_and_wait_page_selector(ctx, embed=embed, func=self.format_all_songs_embed, page=page, db_name='songs')
    
    @commands.command(name = 'songname')
    async def songname(self, ctx, *, message =None):
        for song in self.db["songs"]:
            if song.title is not None:
                if song.title.lower() == message.lower():
                    await ctx.channel.send(embed=self.format_song(song))

                    return
        
        await ctx.channel.send('Did not find a song with that name.')
    

    @commands.command(name = 'join')
    async def join(self, ctx):
        try:
            channel = ctx.message.author.voice.channel
            voice = get(self.bot.voice_clients, guild = ctx.guild)

            if voice and voice.is_connected():
                await voice.move_to(channel)
            else:
                voice = await channel.connect()

            print('Bot connected to', channel)
            return True
        except Exception as e:
            print(e)
            await ctx.channel.send('You must be in a voice channel first.')
            return False
    
    @commands.command(name = 'leave', help = 'leave the voice channel that the bot is in')
    async def leave(self, ctx):
        channel = ctx.message.author.voice.channel
        voice = get(self.bot.voice_clients, guild = ctx.guild)

        if voice and voice.is_connected():
            self.loop_state = False
            await voice.disconnect()
            print('Bot disconnected from', channel)
        else:
            await ctx.send('Not in the voice channel')
    
    @commands.command(name = 'pause', help = 'pauses the song playing', aliases = ['pa'])
    async def pause(self, ctx):
        voice = get(self.bot.voice_clients, guild = ctx.guild)

        if voice and voice.is_playing():
            print('Pausing audio')
            voice.pause()
            await ctx.send('Paused audio')
        else:
            print('Music not playing')
    
    @commands.command(name = 'resume', aliases = ['r'])
    async def resume(self, ctx):
        voice = get(self.bot.voice_clients, guild = ctx.guild)

        if voice and voice.is_paused():
            print('Resuming audio')
            voice.resume()
            await ctx.send('Resumed audio')
        else:
            print('Music not paused')
    
    @commands.command(name = 'stop', help = 'stops the song', aliases = ['s'])
    async def stop(self, ctx):
        voice = get(self.bot.voice_clients, guild = ctx.guild)

        self.loop_state = False

        if voice and (voice.is_playing() or voice.is_paused()):
            print('Stopping audio')
            voice.stop()
            await ctx.send('Stopped audio')
        else:
            print('Music not playing')
    

    @commands.command(name = 'loop', aliases = ['l'])
    async def loop(self, ctx):
        if self.loop_state:
            self.loop_state = False
            await ctx.send('Turned loop off!')
        else:
            self.loop_state = True
            await ctx.send('Turned loop on!')


    @commands.command(name = 'play')
    async def playsong(self, ctx, *, id = None):
        link = ''
        youtube = False

        if id is not None and id.isdigit():
            for song in self.db["songs"]:
                if song.id == int(id):
                    link = song.bgm
                    await ctx.channel.trigger_typing()
        
        elif id is not None:
            link = id 
            youtube = True
        
        else:
            await ctx.channel.send('No song id provided.')
            return
        

        #########################################################
        ## play song from downloaded mp3.

        if not await self.join(ctx):
            return
        
        def check_queue():
            if not self.loop_state:
                queue_in_file = os.path.isdir('./queue')
                if queue_in_file:
                    dir = os.path.abspath(os.path.realpath('queue'))
                    length_queue = len(os.listdir(dir))
                    still_a_queue = length_queue - 1

                    try:
                        first_file = os.listdir(dir)[0]
                    except:
                        print('No more songs in the queue')
                        self.queue.clear()
                        return

                    main_location = os.path.dirname(os.path.realpath('bandori-cord'))
                    song_path = os.path.abspath(os.path.realpath('queue') + '\\' + first_file)

                    if length_queue != 0:
                        print('song done, playing next in queue')
                        print('songs still in queue', still_a_queue)
                        song_in_there = os.path.isfile('song.mp3')
                        if song_in_there:
                            os.remove('song.mp3')
                        shutil.move(song_path, main_location)

                        for file in os.listdir('./'):
                            if file.endswith('.mp3'):
                                os.rename(file, 'song.mp3')

                        voice.play(discord.FFmpegPCMAudio('song.mp3'), after = lambda e: check_queue())
                        voice.source = discord.PCMVolumeTransformer(voice.source)
                        voice.source.volume = 1.0

                    else:
                        self.queue.clear()
                        return

                else:
                    self.queue.clear()
                    print('No songs queued before the ending of the last song')
                    return
            else:
                voice.play(discord.FFmpegPCMAudio('song.mp3'), after = lambda e: check_queue())
                voice.source = discord.PCMVolumeTransformer(voice.source)
                voice.source.volume = 1.0
        


        check_song = os.path.isfile('song.mp3')
        try:
            if check_song:
                os.remove('song.mp3')
                self.queue.clear()
                print('Removed old song file')
        except PermissionError:
            print('Trying to delete old song file failed because it\'s being used')
            await ctx.send('Music is already playing. Stop the current song, or queue your song.')
            return


        queue_in_file = os.path.isdir('./queue')
        try:
            queue_folder = './queue'
            if queue_in_file:
                print('Removed old queue folder')
                shutil.rmtree(queue_folder)
        except:
            print('No old queue folder')

        if not youtube:
            async with aiohttp.ClientSession() as session:
                async with session.get(link) as resp:
                    if resp.status != 200:
                        return await ctx.channel.send('Could not download file...')
                    data = io.BytesIO(await resp.read())
            
            with open(f'song.mp3', 'wb') as outf:
                outf.write(data.getbuffer())

        else:
            loop = asyncio.get_event_loop()
            job_result = await loop.run_in_executor(None, self.youtube_download, link)

            if job_result:
                print('Downloaded song')

        voice = get(self.bot.voice_clients, guild = ctx.guild)


        voice.play(discord.FFmpegPCMAudio(f'song.mp3'), after = lambda e: check_queue())
        voice.source = discord.PCMVolumeTransformer(voice.source)
        voice.source.volume = 1.0

        #await ctx.channel.send(f'Now playing: [{song.title} - {song.band_name}]')
        return
    
        

        
    

    @commands.command(name = 'queue', aliases = ['q'])
    async def queue(self, ctx, *, id):

        queue_in_file = os.path.isdir('./queue')

        if not queue_in_file:
            os.mkdir('queue')
        dir = os.path.abspath(os.path.realpath('queue'))

        queue_number = len(os.listdir(dir))
        queue_number += 1

        while True:
            if queue_number in list(self.queue.keys()):
                queue_number += 1
            else:
                self.queue[queue_number] = queue_number
                break

        queue_path = os.path.abspath(os.path.realpath('queue') + f'/song{queue_number}.mp3')

        if id is not None and id.isdigit():
            for song in self.db["songs"]:
                if song.id == int(id):
                    await ctx.channel.trigger_typing()

                    async with aiohttp.ClientSession() as session:
                        async with session.get(song.bgm) as resp:
                            if resp.status != 200:
                                return await ctx.channel.send('Could not download file...')
                            data = io.BytesIO(await resp.read())
                    
                    with open(f'{queue_path}', 'wb') as outf:
                        outf.write(data.getbuffer())
        
        elif id is not None:
            loop = asyncio.get_event_loop()
            job_result = await loop.run_in_executor(None, self.youtube_download, id, queue_path, True)

            if job_result:
                print('Downloaded song')

        
        await ctx.send(f'Added to queue')

    @commands.command(name = 'skip', aliases = ['next'])
    async def skip(self, ctx):
        voice = get(self.bot.voice_clients, guild = ctx.guild)

        if voice and voice.is_playing():
            print('Stopping audio')
            voice.stop()
            await ctx.send('Skipped audio')
        else:
            print('Music not playing')
        

    def format_song(self, song):
        embed = discord.Embed(title = song.title)

        embed.set_image(url=song.jacket)
        embed.set_thumbnail(url=song.thumb)
        
        embed.add_field(name = 'Band', value=f'[{song.band}] {song.band_name}', inline=False)
        embed.add_field(name = 'Lyricist', value=song.lyricist)
        embed.add_field(name = 'Composer', value=song.composer)
        embed.add_field(name = 'Arranger', value=song.data["arranger"])
        embed.add_field(name = 'How to get', value=song.how_to_get, inline=False)

        embed.add_field(name = 'Difficulty', value=f'{song.difficulty}\n\
            **Easy** :blue_circle:: {song.difficulty[0]}\
            **Normal** :green_circle:: {song.difficulty[3]}\n\
            **Hard** :yellow_circle:: {song.difficulty[2]}\
            **Expert** :red_circle:: {song.difficulty[1]}')
        
        embed.set_footer(text = f'Song id: {song.id} | Listen to me! Enter the command: ;play {song.id}')

        return embed
    

    def format_all_songs_embed(self, data, page=0, filters={}):
        page, total_pages, new_data, start, end = self.page_logic(data=data, page=page, filters=filters)

        songs_page = [song for song in new_data[start:end]]

        embed = discord.Embed(title='List of Music')

        for s in songs_page:
            embed.add_field(name=s.id, value=f'{s.title} | {s.band_name}', inline=False)
        
        embed.set_footer(text=f'Page {page} of {total_pages}')

        return page, embed
    

    def youtube_download(self, url, path=None, queue=False):
        if path:
            ydl_opts = {'format': 'bestaudio/best', 'default_search': 'ytsearch', 'outtmpl': path,\
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}]}
        else:
            ydl_opts = {'format': 'bestaudio/best', 'default_search': 'ytsearch',\
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}]}

        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            print('Downloading audio')

            ydl.download([url])
        
        if not queue:
            for file in os.listdir('./'):
                #print(file)
                if file.endswith('.mp3'):
                    name = file
                    print('Renamed file:', file)

                    os.rename(file, 'song.mp3')


   
    











def setup(bot):
    bot.add_cog(BandoriViewer(bot))