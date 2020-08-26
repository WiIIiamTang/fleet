from discord.ext import tasks, commands
from pydori import bandori_api
import asyncio
import discord

class BandoriTasks(commands.Cog):
    '''
    Manage automatic tasks that runs on an interval
    '''
    UPDATE_CHANNEL_ID = 748253854688083988 # put your channel id here.
    MESSAGE_IDS = {}

    def __init__(self, bot):
        self.bot = bot
        self.bapi = bandori_api()
        self.bapi2 = bandori_api(party=False)

        self.info_update.start()

    @tasks.loop(hours=24)
    async def info_update(self):
        await asyncio.sleep(5)
        channel = self.bot.get_channel(BandoriTasks.UPDATE_CHANNEL_ID)

        tasks = [ self.active_gachas,
                  self.active_events
                  ]
        
        for task in tasks:
            await task(channel)
        
        print('Updated info board.')
    

    async def active_gachas(self, channel):
        current = self.bapi2.get_active_gachas()
        
        gachas = [(e.name, e.id, e) for e in current]
        embed = discord.Embed(title='__Bandori current active gachas__')
        for gacha in gachas:
            embed.add_field(name = gacha[0],
                value = f'id: {gacha[1]}\n{gacha[2].get_start_date().strftime("%m/%d/%Y")} - {gacha[2].get_end_date().strftime("%m/%d/%Y")}',
                inline=False)
        
        image = self.bapi.get_items(id=[1])[0]
        embed.set_thumbnail(url=image.image)

        try:
            message = await channel.fetch_message(BandoriTasks.MESSAGE_IDS['g'])
            await message.edit(embed=embed)
        
        except Exception as e:
            m = await channel.send(embed=embed)
            BandoriTasks.MESSAGE_IDS['g'] = m.id

    async def active_events(self, channel):
        event = self.bapi.get_current_event()

        embed = discord.Embed(title = 'Current ongoing event:\n' + event.name)

        main = event.get_main_card()
        boostm = [m.name for m in event.get_boost_members()]
        start = event.get_start_date().strftime("%m/%d/%Y")
        end = event.get_end_date().strftime("%m/%d/%Y")
        
        embed.set_image(url=event.data['english_image'])
        embed.set_thumbnail(url=main.image_trained)

        embed.add_field(name = 'Name', value = event.name)
        embed.add_field(name = 'Type', value = event.type)
        embed.add_field(name = 'Date', value = f'From {start}\nto {end}', inline=False)
        embed.add_field(name = 'Main card', value = (main.name, main.id), inline=False)
        
        embed.add_field(name = 'Boost attribute', value = event.boost_attribute, inline=False)
        embed.add_field(name = 'Boost members', value = boostm, inline=False)


        try:
            message = await channel.fetch_message(BandoriTasks.MESSAGE_IDS['e'])
            await message.edit(embed=embed)
        
        except Exception as e:
            m = await channel.send(embed=embed)
            BandoriTasks.MESSAGE_IDS['e'] = m.id




################################################################################
# add cog to bot.
def setup(bot):
    bot.add_cog(BandoriTasks(bot))
