import discord
from discord.ext import commands, tasks
import valve.source.a2s
import valve.rcon
import random
import logging
import os
from dotenv import load_dotenv
from cogs.bin.pickup import Game, GameOnError, GameNotOnError, PlayerAddedError, GameFullError, TeamFullError, PlayerNotAddedError
from cogs.bin.player import Player

class PUG(commands.Cog, name="Pick-up Game"):

    log_format = logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s')
    logger = logging.getLogger('pug')
    logger.setLevel(logging.INFO)
    file_handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
    file_handler.setFormatter(log_format)
    logger.addHandler(file_handler)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_format)
    logger.addHandler(console_handler)

    def __init__(self, client):
        load_dotenv()
        self.reset_password.start()
        self.client = client
        self.client.ctx = None
        self.game_guild = int(os.getenv('PRIMARY_GUILD'))
        # self.game_channel = int(os.getenv('PRIMARY_CHANNEL'))
        # self.empty_slot = "(?)"
        # self.game_on = False
        # self.game_full = False
        # self.player_count = 0
        # self.max_players = 12
        # self.start_delay = 10
        # self.players = []
        self.game_message = None
        self.servers = eval(os.getenv('PUG_SERVERS'))
        self.passwords = eval(os.getenv('PUG_PASSWORDS'))
        self.game_server = None
        self.game_password = None
        self.rcon_password = os.getenv('RCON_PASSWORD')
        self.map_pool = eval(os.getenv('MAP_POOL'))
        self.game_map = None
        self.used_servers = []
        self.channels = eval(os.getenv('PUG_CHANNELS'))
        self.chaninfo = {}
        self.pug_init()

    def pug_init(self):
        for channel in self.channels:
            self.chaninfo[channel] = {}
            self.chaninfo[channel]['ctx'] = None
            self.chaninfo[channel]['game_full'] = False
            self.chaninfo[channel]['game_message'] = None
            self.chaninfo[channel]['game_server'] = None
            self.chaninfo[channel]['game_password'] = None
            self.chaninfo[channel]['game_map'] = None
            self.chaninfo[channel]['player_count'] = 0
            self.chaninfo[channel]['added_players'] = {}
            game = Game(2, 6)
            self.chaninfo[channel]['game'] = game

    # @commands.Cog.listener()
    # async def on_reaction_add(self, reaction, user):
    #     channel = reaction.message.channel
    #     await channel.send(f'{user.name} added {reaction.emoji} to "{reaction.message.content}"')

    ## # # # # # # # # ##
    # Helper Decorators #
    ## # # # # # # # # ##

    ## # # # # # # #
    # Bot commands #
    ## # # # # # # #

    @commands.command(help="- Starts a pick-up game")
    @commands.has_any_role('admin', 'pug-admin', 'captain')
    async def start(self, ctx, teams=2, mode="6v6"):
        context = self.chaninfo[ctx.channel.id]
        self.logger.info(f"{ctx.message.author} triggered start()")

        if ctx.message.guild.id != self.game_guild:
            return
            
        if ctx.message.channel.id not in self.chaninfo.keys():
            return

        if context['game'].game_on:
            await ctx.send(f'Game already on')
            return

        if not context['game'].game_on:
            # self.game_server = await self.find_server()
            # if self.game_server is None:
            #     await ctx.send("No open servers to use, not starting")
            #     return
            # if self.game_server in self.used_servers:
            #     self.used_servers.remove(self.game_server)
            # context['game'].game_on = True
            # context['game'].max_players = size
            context['game_map'] = random.choice(self.map_pool)
            try:
                context['game'].start(teams, mode)
            except GameOnError as e:
                await ctx.send(f'{e}')
                return

            await ctx.send(f'Game started!')
            context['game_message'] = await ctx.send(context['game'].status())
            await context['game_message'].pin()
            # await self.change_password(address=self.game_server, password="temppassword")
        return

    @commands.command(help="- Stops an active pick-up game")
    @commands.has_any_role('admin', 'pug-admin', 'captain')
    async def stop(self, ctx):
        context = self.chaninfo[ctx.channel.id]
        self.logger.info(f"{ctx.message.author} triggered stop()")

        if ctx.message.guild.id != self.game_guild:
            return
            
        if ctx.message.channel.id not in self.chaninfo.keys():
            return

        if not context['game'].game_on:
            await ctx.send(f'No game on.')
            return

        if context['game'].game_on:
            try:
                context['game'].stop()
                await context['game_message'].unpin()
                await ctx.send("Game stopped.")
            except (GameOnError, GameNotOnError) as e:
                await ctx.send(f'{e}')
                return
        return

    @commands.command(aliases=['re'], help="- Restarts an active pick-up game. Can take an integer argument for the size of the new pug")
    @commands.has_any_role('admin', 'pug-admin', 'captain')
    async def restart(self, ctx, size=0):
        context = self.chaninfo[ctx.channel.id]
        self.logger.info(f"{ctx.message.author} triggered restart()")

        if ctx.message.guild.id != self.game_guild:
            return
            
        if ctx.message.channel.id not in self.chaninfo.keys():
            return
            
        if not context['game'].game_on:
            await ctx.send(f'No game on.')
            return

        if context['game'].game_on:
            try:
                await context['game_message'].unpin()
                context['game'].restart(1, 12)
                await ctx.send(f'Game restarted!')
                context['game_message'] = await ctx.send(context['game'].status())
                await context['game_message'].pin()
            except GameOnError as e:
                await ctx.send(f'{e}')
                return
        return

    @commands.command(help="- Checks the status of an active pick-up game")
    async def status(self, ctx):
        context = self.chaninfo[ctx.channel.id]
        self.logger.info(f"{ctx.message.author} triggered status()")

        if ctx.message.guild.id != self.game_guild:
            return
            
        if ctx.message.channel.id not in self.chaninfo.keys():
            return

        if not context['game'].game_on:
            await ctx.send(f'No game on.')
            return

        if context['game'].game_on:
            await ctx.send(context['game'].status())
        return

    @commands.command(help="- Adds yourself to an active pick-up game")
    @commands.has_any_role('player')
    async def add(self, ctx):
        context = self.chaninfo[ctx.channel.id]
        self.logger.info(f"{ctx.message.author} triggered add()")

        if ctx.message.guild.id != self.game_guild:
            return
            
        if ctx.message.channel.id not in self.chaninfo.keys():
            return

        if not context['game'].game_on:
            await ctx.send(f'No game on.')
            return

        if ctx.message.author.id in context['added_players'].keys():
            await ctx.send(f'Already added.')
            return

        for key, value in self.chaninfo.items():
            print(f'Key {key}, Value {value}')
            if ctx.message.author.id in value['added_players'].keys():
                await ctx.send(f'Already added elsewhere.')
                return

        player = Player(ctx.message.author, 0)

        try:
            context['added_players'][ctx.message.author.id] = player
            context['game'].add(context['added_players'][ctx.message.author.id])
        except (PlayerAddedError, GameFullError, TeamFullError) as e:
            del context['added_players'][ctx.message.author.id]
            await ctx.send(f'{e}')
            return
        
        await self.game_update_pin(ctx.channel.id)
        context['player_count'] += 1
        await ctx.send(context['game'].status())
        #try start game?
        return

    @commands.command(aliases=['rem'], help="- Removes yourself from an active pick-up game")
    async def remove(self, ctx):
        context = self.chaninfo[ctx.channel.id]
        self.logger.info(f"{ctx.message.author} triggered remove()")

        if ctx.message.guild.id != self.game_guild:
            return
            
        if ctx.message.channel.id not in self.chaninfo.keys():
            return

        if not context['game'].game_on:
            await ctx.send(f'No game on')
            
        if context['game'].game_on:
            try:
                context['game'].remove(context['added_players'][ctx.message.author.id])
            except (GameNotOnError, PlayerNotAddedError, KeyError) as e:
                await ctx.send(f'{e}')
                return

        await self.game_update_pin(ctx.channel.id)
        await ctx.send(context['game'].status())
        return

    @commands.command(aliases=['pk'], hidden=True)
    @commands.has_any_role('admin', 'pug-admin', 'captain')
    async def playerkick(self, ctx, member : discord.Member):
        context = self.chaninfo[ctx.channel.id]
        self.logger.info(f"{ctx.message.author} triggered playerkick()")

        if ctx.message.guild.id != self.game_guild:
            return
            
        if ctx.message.channel.id not in self.chaninfo.keys():
            return

        if not context['game'].game_on:
            await ctx.send(f'No game on')

        if context['game'].game_on:
            try:
                context['game'].remove(context['added_players'][member.id])
                await self.game_update_pin(ctx.channel.id)
                await ctx.send(context['game'].status())
            except (GameNotOnError, PlayerNotAddedError) as e:
                await ctx.send(f'{e}')
                return

    @commands.command(help="- Changes the map of the active game")
    @commands.has_any_role('admin', 'pug-admin', 'captain')
    async def map(self, ctx, map):
        self.logger.info(f"{ctx.message.author} triggered map()")
        if ctx.message.guild.id == self.game_guild and ctx.message.channel.id == self.game_channel:
            if map in self.map_pool:
                self.game_map = map
                await ctx.send(f"Map changed to {self.game_map}")
                await ctx.send(await self.game_status())
            else:
                await ctx.send(f"Invalid map name, !maps to see valid maps.")

    @commands.command(help="- Lists the maps in the map pool")
    @commands.has_any_role('player')
    async def maps(self, ctx):
        self.logger.info(f"{ctx.message.author} triggered maps()")
        if ctx.message.guild.id == self.game_guild and ctx.message.channel.id == self.game_channel:
            await ctx.send(f"Map pool: {', '.join(self.map_pool)}")

    ## # # # # # # # #
    # Game functions #
    ## # # # # # # # #

    # async def game_status(self):
    #     lineup = []
    #     empty = []
    #     for player in self.players:
    #         if player != self.empty_slot:
    #             lineup.append(player.name)
    #         else:
    #             empty.append(player)
    #     return f'({self.game_map}) Players [{self.player_count}/{self.max_players}]: {", ".join(lineup + empty)}'

    async def game_reset(self, size=0):
        if self.game_on:
            if self.game_message:
                await self.game_message.unpin()
            if size:
                self.max_players = size
            self.game_full = False
            self.player_count = 0
            self.players = [self.empty_slot for x in range(self.max_players)]
            return True
        else:
            return False
    
    async def game_stop(self):
        if self.game_on:
            self.game_on = False
            self.player_count = 0
            self.max_players = 12
            self.players = []
            self.game_server = None
            await self.game_message.unpin()
            return True
        else:
            return False

    async def game_start(self, ctx):
        if self.player_count == self.max_players:
            self.game_full = True
            await ctx.send('Game is full. Waiting 60 seconds before game starts.')
            self.client.ctx = ctx
            self.game_countdown.start()

    async def find_server(self):
        self.logger.info("Looking for an open server")
        for address in self.servers:
            try:
                with valve.source.a2s.ServerQuerier(address) as server:
                    server_name = server.info()["server_name"]
                    player_count = server.info()["player_count"]
                    self.logger.info(f"Server {server_name} has {player_count} players")
                    if player_count < 1:
                        return (server.host, server.port)
            except valve.source.NoResponseError:
                self.logger.warning(f"Could not query server {address} to see if it is open")
                pass

    async def change_password(self, address, password):
        command = f"sv_password {password}"
        valve.rcon.execute(address, self.rcon_password, command)

    async def game_update_pin(self, chan):
        context = self.chaninfo[chan]
        await context['game_message'].edit(content=(context['game'].status()))
        # await self.game_message.edit(content=(await self.game_status()))

    ## # # # # # # # # #
    # Player functions #
    ## # # # # # # # # #

    async def player_add(self, player):
        if player not in self.players:
            for index, slot in enumerate(self.players):
                if slot == self.empty_slot:
                    self.players[index] = player
                    self.player_count += 1
                    break
            if self.player_count == self.max_players:
                self.game_full = True
            return True
        else:
            return False

    async def player_remove(self, player):
        if player in self.players:
            self.players.remove(player)
            new_list = []
            for slot in self.players:
                if slot != self.empty_slot:
                    new_list.append(slot)
            while len(new_list) < self.max_players:
                new_list.append(self.empty_slot)
            self.players = new_list
            self.player_count -= 1
            if self.player_count < self.max_players:
                self.game_full = False
            return True
        else:
            return False

    ## # # # # # # # #
    # Loop functions #
    ## # # # # # # # #

    # @tasks.loop(seconds=1, count=60)
    @tasks.loop(seconds=1, count=5)
    async def game_countdown(self):
        if not self.game_full:
            self.logger.info("Game is no longer full, cancelling.")
            self.game_countdown.cancel()
        else:
            self.logger.info("Game is still full, continuing countdown")

    @game_countdown.after_loop
    async def game_countdown_decision(self):
        self.logger.info("Reached game_countdown_decision")
        if self.game_countdown.is_being_cancelled():
            await self.client.ctx.send('No longer full, cancelling countdown')
        else:
            self.reset_password.restart()
            await self.client.ctx.send(f'Game commencing! PM\'ing connection details to all players')
            valve.rcon.execute(self.game_server, self.rcon_password, f"changelevel {self.game_map}")
            self.game_password = random.choice(self.passwords)
            for player in self.players:
                await player.send(f'Your Pick-up Game is ready. Please connect to steam://connect/{self.game_server[0]}:{self.game_server[1]}/{self.game_password}')
                lineup = await self.game_status()
                await player.send(f'{lineup}')
            await self.change_password(address=self.game_server, password=f'{self.game_password}')
            self.used_servers.append(self.game_server)
            await self.game_stop()
            
    @tasks.loop(seconds=600)
    async def reset_password(self):
        self.logger.info("Checking for a server password to reset")
        if self.used_servers:
            for address in self.used_servers:
                self.logger.info(f"Trying to reset password for server {address}")
                try:
                    with valve.source.a2s.ServerQuerier(address) as server:
                        player_count = server.info()["player_count"]
                        server_name = server.info()["server_name"]
                        if player_count < 1:
                            self.logger.info(f"Changing sv_password of server {server_name}")
                            valve.rcon.execute(address, self.rcon_password, "sv_password wedontreallycare")
                            self.used_servers.remove(address)
                        else:
                            self.logger.info(f"Server {server} still in use, not changing password")
                except valve.source.NoResponseError:
                    self.logger.warn(f"Could not connect to {address}")
                    pass

    ## # # # # # # # # # # # #
    # Cleanup when unloading #
    ## # # # # # # # # # # # #

    def cog_unload(self):
        self.logger.info("Extension pug is being unloaded!")
        self.logger.handlers = []
        self.reset_password.cancel()
        # self.game_stop()

def setup(client):
    client.add_cog(PUG(client))
