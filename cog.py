from discord.ext import commands
import voice_data as vd


class Cog(commands.Cog):
    def __init__(self, bot_client: commands.Bot, voice_module):
        self.bot = bot_client
        self._last_member = None
        self.voice_module = voice_module

    @commands.command()
    async def atb_help(self, ctx: commands.context.Context):
        default_voice_message = "\nHere is default voice setting:"
        for (key, value) in self.voice_module.iso_mapping_list.items():
            default_voice_message += f"\n       auto-{key} : {value['ShortName']}"
            if len(default_voice_message) > 1000:
                default_voice_message = default_voice_message[:1000]

        string = "How to use this client:" \
                 "\n        Type __`你好__ or __'Hello__" \
                 "\n        Bot will detects language automatically" \
                 + default_voice_message + \
                 "\n" \
                 "\nYou can setup your own voice setting." \
                 "\nUse command __!search (key1) (key2)__ to search usable voice name" \
                 "\nAnd use __!set_voice (custom_key) (voice_name)__" \
                 "\n           Or __!set_voice (default_voice_key) (voice_name)__" \
                 "\nExample:" \
                 "\n!set_voice auto-en en-GB-LibbyNeural" \
                 "\nThis command will make auto detected English message play with this voice." \
                 "\n!set_voice test ko-KR-InJoonNeural" \
                 "\n        And you can use [ko-KR-InJoonNeural] voices by tying __`test 안녕__" \
                 "\nVisit here to hear sample audio:" \
                 "\nhttps://azure.microsoft.com/en-us/services/cognitive-services/text-to-speech/#features" \
                 "\n" \
                 "\ntype __!command__ for more command information"
        await ctx.send(string)

    @commands.command()
    async def command(self, ctx: commands.context.Context):
        string = "\nCommand list:" \
                 "\n`!leave`" \
                 "\nLet client leave the voice channel" \
                 "\n" \
                 "\n`!update_voice_list`" \
                 "\nUpdate voice list from microsoft official website" \
                 "\n" \
                 "\n`!show_voice_setting`" \
                 "\nShows a list of your voice custom setting" \
                 "\n" \
                 "\n`!delete_profile`" \
                 "\nDelete your profile" \
                 "\n" \
                 "\n`!delete_voice_setting (key)`" \
                 "\nDelete your voice setting with key" \
                 "\n" \
                 "\n`!set_voice (custom_key) (voice_name)`" \
                 "\nSet voice with specific key" \
                 "\n" \
                 "\n`!set_default_voice (voice_name)`" \
                 "\nWhen u didn't define the language, this voice will be chosen" \
                 "\n" \
                 "\n`!search (key1) (key2)`" \
                 "\nSearch for a voice"
        await ctx.send(string)

    @commands.command()
    async def leave(self, ctx: commands.context.Context):
        """
        Let client leave the voice channel
        :param ctx: commands.context.Context
        :return: nothing
        """
        bot_voice_client = next(
            (voice_client for voice_client in self.bot.voice_clients
             if voice_client.guild == ctx.author.guild), None)
        if bot_voice_client:
            await bot_voice_client.disconnect()
            await ctx.send("Voice channel left")
        else:
            await ctx.send("Not in a voice channel")

    @commands.command()
    async def update_voice_list(self, ctx: commands.context.Context):
        self.voice_module.voice_list = vd.get_voice_list_from_microsoft()
        await ctx.send("Done!")

    @commands.command()
    async def set_voice(self, ctx: commands.context.Context, key, voice_name):
        # Get user voice data
        user_voice_data = self.voice_module.get_user_data(str(ctx.author.id), False)
        if not user_voice_data.user_id:
            user_voice_data.user_id = str(ctx.author.id)
            user_voice_data.user_name = ctx.author.name
    
        # Search for voice data
        voice_search_data = self.voice_module.search(voice_name)
        if len(voice_search_data) == 1:
            # Set voice
            user_voice_data.voice_setting[key] = self.voice_module.search(voice_name).pop()
            # Save voice data
            self.voice_module.save_user_data(user_voice_data)
            await ctx.send(f"set_voice: {voice_name}")
        else:
            await ctx.send(f"Wrong voice name! : {voice_name}\n"
                           f"Use !search or visit\n"
                           f"https://docs.microsoft.com/en-us/azure/cognitive-services/speech-service/"
                           f"language-support#prebuilt-neural-voices\n"
                           f"to get correct voice name!")

    @commands.command()
    async def set_default_voice(self, ctx: commands.context.Context, key, voice_name):
        result = self.voice_module.set_iso_mapping_data(key, voice_name)
        await ctx.send(result)

    @commands.command()
    async def set_default_voice_auto(self, ctx: commands.context.Context):
        count_success = 0
        count_fail = 0
        for item in self.voice_module.iso_mapping_list.items():
            if type(item[1]) != dict:
                result = self.voice_module.set_iso_mapping_data(item[0], item[0] + '-', True)
                if result == 'Voice set':
                    count_success += 1
                elif result == 'Wrong voice name':
                    count_fail += 1
        await ctx.send(f'Done. success:{count_success} fail:{count_fail}')

    @commands.command()
    async def search(self, ctx: commands.context.Context, search_key1: str, search_key2=""):
        voice_data_search_list = self.voice_module.search(search_key1, search_key2)
    
        result = ""
        for voice_data in voice_data_search_list:
            result += f"{voice_data.short_name} {voice_data.gender} {voice_data.locale_name}\n"
    
        if voice_data_search_list:
            if len(result) > 2000:
                result = result[:1950] + "........\n........."
            await ctx.send(f"Search result:\n{result}")
        else:
            await ctx.send(f"No data found")

    @commands.command()
    async def show_voice_setting(self, ctx: commands.context.Context):
        # Get user voice data
        user_voice_data = self.voice_module.get_user_data(str(ctx.author.id), False)
        if not user_voice_data.user_id:
            await ctx.send(f"User profile doesn't exist!")
        else:
            result = "Here is your voice setting\n" \
                     "---------------------------------\n"
            for (key, value) in user_voice_data.voice_setting.items():
                result += f"{key} : {value.short_name}\n"
            result += "---------------------------------\n"
            await ctx.send(f"{result}")

    @commands.command()
    async def delete_voice_setting(self, ctx: commands.context.Context, key):
        # Get user voice data
        user_voice_data = self.voice_module.get_user_data(str(ctx.author.id), False)
        if not user_voice_data.user_id:
            await ctx.send(f"User profile doesn't exist!")
        else:
            if key in user_voice_data.voice_setting:
                user_voice_data.voice_setting.pop(key)
                self.voice_module.save_user_data(user_voice_data)
                await ctx.send(f"Setting {key} deleted!")
            else:
                await ctx.send(f"Wrong key!\nPlease check your voice setting by using !show_voice_setting")

    @commands.command()
    async def delete_profile(self, ctx: commands.context.Context):
        # Get user voice data
        user_voice_data = self.voice_module.get_user_data(str(ctx.author.id), False)
        if not user_voice_data.user_id:
            await ctx.send(f"User profile doesn't exist!")
        else:
            self.voice_module.delete_user_data(user_voice_data)
            await ctx.send(f"Your profile has been deleted!")
