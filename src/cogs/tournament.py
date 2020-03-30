import asyncio
import logging
import random
from os import getenv

import discord
from discord.ext import commands
from utils.groups import make_groups


class TournamentCog(commands.Cog, name="Tournament Helper"):
    """Creates Tournament Brackets!"""

    def __init__(self, bot):
        self.bot: commands.Bot = bot
        self.category = int(692803392031948911)  # gaming tournament
        self.gamers = []  # initialize the epic people
        self.role_student = int(getenv('ROLE_STUDENT', 689214914010808359))  # student role
        self.join_message = None
        self.enabled = True
        self.games = {}
        self.status_message = None
        self.round = 0

    @commands.group(name="tournament")
    async def tournament(self, ctx):
        """Contains tournament subcommands, do '~help tournament' for more info"""
        if ctx.invoked_subcommand is None:
            await ctx.send('Invalid team command passed...')

    @tournament.command(name="create")
    @commands.has_any_role('Tournament Master')
    async def tourney_create(self, ctx: commands.context.Context, game_name: str, emoji=':trophy:'):
        """Creates a tournament with the given name and reaction emoji."""
        await ctx.message.delete()
        self.gamers = []
        self.enabled = True
        self.round = -1
        logging.debug("Starting tournament creation...")
        # Creates a new channel for the tournament
        self.game_name = game_name
        self.emoji = emoji
        self.overwrites = {
            ctx.guild.default_role: discord.PermissionOverwrite(send_messages=False),
            ctx.guild.get_role(self.role_student): discord.PermissionOverwrite(send_messages=False),
            ctx.guild.me: discord.PermissionOverwrite(read_messages=True)
        }
        self.tc = ctx.channel
        # Creates and sends the join message
        self.join_message: discord.Message = await ctx.channel.send(
            make_join_message(game_name, emoji, self.gamers)
        )
        await self.join_message.add_reaction('🏆')

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.event_type == "REACTION_ADD" and payload.emoji.name == '🏆' and payload.message_id == self.join_message.id and self.enabled is True:
            if payload.user_id != self.bot.user.id:  # John must not become gamer
                self.gamers.append(payload.user_id)
            await self.join_message.edit(content=make_join_message(self.game_name, self.emoji, self.gamers))

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        if payload.event_type == "REACTION_REMOVE" and payload.emoji.name == '🏆' and payload.message_id == self.join_message.id and self.enabled is True:
            self.gamers.remove(payload.user_id)
            await self.join_message.edit(content=make_join_message(self.game_name, self.emoji, self.gamers))

    @tournament.command(name="round")
    @commands.has_any_role('Tournament Master')
    async def tourney_round(self, ctx: commands.context.Context, groupSize=4):
        """Creates a round of matches of the specified size."""
        random.shuffle(self.gamers)
        self.round += 1
        await ctx.message.delete()
        self.enabled = False
        groups = make_groups(self.gamers, groupSize)
        self.games = await create_games(groups=groups, ctx=ctx, game_name=self.game_name, overwrites=self.overwrites,
                                        category=self.category)
        for game in self.games:
            for gamer in self.games[game]['gamers']:
                if gamer is not None:
                    await self.games[game]['tc'].set_permissions(ctx.guild.get_member(gamer),
                                                                 read_messages=True,
                                                                 manage_messages=True)
                    await self.games[game]['vc'].set_permissions(ctx.guild.get_member(gamer),
                                                                 read_messages=True,
                                                                 send_messages=True)

            await ctx.guild.get_channel(self.games[game]['tc'].id).send(
                f'''Cowabunga, Gamers! :cowboy:
Welcome to the Game Tournament! Please join the associated voice channel. It is now time to fight your fellow comrades. When you are finished, please use the command ~winner with who won.
Game on! {''.join([f'<@{gamer}> ' for gamer in self.games[game]['gamers'] if gamer != None])}'''
            )
            await ctx.guild.get_channel(self.games[game]['tc'].id).send(
                f'''<@{random.choice(self.games[game]['gamers'])}> has been randomly selected as the game host. Please send them a link to your steam profile so y'all can begin the HIGH OCTANE GAMING ACTION! :race_car:'''
            )
            await self.tc.send(f'Round {self.round} has started!')
        self.join_message = await self.tc.send(make_running_message(self.game_name, self.games, self.round))
        self.gamers = []

    @tournament.command(name="winner-set", aliases=["winner_set", "round-winner-set", "round_winner_set"])
    @commands.has_any_role('Tournament Master')
    async def round_winner_set(self, ctx: commands.context.Context, winner):
        """Sets the winner of a round."""
        winner_id = int(winner.replace('<', '').replace('!', '').replace('>', '').replace('@', ''))
        if winner_id in self.games[ctx.channel.id]['gamers']:
            self.gamers.append(winner_id)
            self.games[ctx.channel.id]['winner'] = winner_id
            await self.join_message.edit(content=make_running_message(self.game_name, self.games, self.round))
            if len(self.games) == 1:
                await self.tc.send(
                    f'<@{winner_id}> has won the tournament! Congratulations!~~')
            else:
                await self.tc.send(
                    f'Congratulations to <@{winner_id}> for winning round {self.round} game {self.games[ctx.channel.id]["idx"]}!')
            await asyncio.sleep(5)
            await self.games[ctx.channel.id]['tc'].delete()
            await self.games[ctx.channel.id]['vc'].delete()

    @tournament.command(name="winner",
                        aliases=["round-winner", "round_winner", 'votewinner', 'vote_winner', 'vote-winner',
                                 'roundwinner'])
    async def round_winner(self, ctx: commands.context.Context, winner=None):
        """Votes for the winner of a round."""
        if ctx.channel.id in self.games:
            game = self.games[ctx.channel.id]
        else:
            await ctx.channel.send(
                '''I'm sorry, but this is not a known channel for a round. Please retry your command in a channel for a tournament match.''')
            return
        try:
            winner_id = int(winner.replace('<', '').replace('!', '').replace('>', '').replace('@', ''))
        except:
            await ctx.channel.send('''I'm sorry, I don't know who you're talking about! Please use the command as follows, mentioning the person who won:
            ~winner <@689549152275005513>''')
            return
        if winner_id in game['gamers']:
            self.games[ctx.channel.id]['votes'][ctx.author.id] = winner_id
            game = self.games[ctx.channel.id]
            if game['voting_message'] is None:
                self.games[ctx.channel.id]['voting_message'] = await ctx.channel.send(make_voting_message(game))
            else:
                await self.games[ctx.channel.id]['voting_message'].edit(content=make_voting_message(game))
            if all(vote == game['votes'][ctx.author.id] for vote in game['votes'].values()):
                await self.round_winner_set(ctx=ctx, winner=winner)
        else:
            await ctx.channel.send('''I'm sorry, I don't know who you're talking about! Please use the command as follows, mentioning the person who won:
~winner <@689549152275005513>''')

    @tournament.command(name="delete")
    @commands.has_any_role('Tournament Master')
    async def tourney_delete(self, ctx: commands.context.Context):
        """Deletes the specified tournament."""
        await ctx.message.delete()
        await (await ctx.send('Ok, I deleted the tournament')).delete(delay=5)
        for game in self.games:
            try:
                await self.games[game]['tc'].delete()
            except:
                pass
            try:
                await self.games[game]['vc'].delete()
            except:
                pass

    @tournament.command(name="broadcast")
    @commands.has_any_role('Tournament Master')
    async def tourney_broadcast(self, ctx: commands.context.Context, message):
        """Sends a message to all in-progress games."""
        for game in self.games:
            try:
                await self.games[game]['tc'].send(message)
            except:
                print('Error sending broadcast')


def setup(bot):
    bot.add_cog(TournamentCog(bot))


def make_join_message(game, emoji, gamers):
    msg = f"{game} tournament: react with {emoji} to join!"
    if len(gamers) > 0:
        msg += f"Currently participating - {len(gamers)}:\n"
        if len(gamers) < 50:
            for gamer in gamers:
                msg += f"<@{gamer}\n"
    return msg[:1999]


def make_running_message(game, games, round):
    msg = f'''{game} Tournament:
Current matches (Round {round}):
'''
    for g in games:
        out = f'''Match {games[g]['idx']} - '''
        if games[g]['winner']:
            out += f'''Winner: <@{games[g]['winner']}>
'''
        else:
            out += '''In progress
'''
        msg += out
    return msg[:1999]


async def create_games(groups, ctx, game_name='Gaming', overwrites=None, category=None):
    games = {}
    for idx, group in enumerate(groups):
        tc = await ctx.guild.create_text_channel(name=f"game-{idx}📋",
                                                 overwrites=overwrites,
                                                 category=ctx.guild.get_channel(category),
                                                 topic=f"A channel for the {game_name} tournament!")
        vc = await ctx.guild.create_voice_channel(name=f"game-{idx}🔊",
                                                  overwrites=overwrites,
                                                  category=ctx.guild.get_channel(category),
                                                  topic=f"A channel for the {game_name} tournament!")
        games[tc.id] = {
            'gamers': group,
            'tc': tc,
            'vc': vc,
            'winner': None,
            'idx': idx,
            'voting_message': None,
            'votes': {gamer: None for gamer in group}
        }
    return games

def make_voting_message(game):
    out = f'''Winner for game {game['idx']}:
'''
    for gamer in game['gamers']:
        out += f'''
<@{gamer}> - '''
        if game['votes'][gamer] is None:
            out += 'Not yet voted'
        else:
            out += f'<@{game["votes"][gamer]}>'

    return out[:1999]