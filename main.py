from command import *
import discord
from discord.ext import commands
import os
import azure.cognitiveservices.speech as speech_sdk
from azure.cognitiveservices.speech import AudioDataStream, SpeechSynthesisOutputFormat
import voice_data as vd
import asyncio
import yaml
import langid
from hashlib import sha256

# Load config
with open('config.yml', 'r') as yml:
    config = yaml.safe_load(yml)

# Azure_TTS
# Creates an instance of a speech config with specified subscription key and service region.
AZURE_TTS_TOKEN = config['AZURE_TTS_TOKEN']
speech_key, service_region = AZURE_TTS_TOKEN, "japaneast"
speech_config = speech_sdk.SpeechConfig(subscription=speech_key, region=service_region)

# discord
# bot = discord.Client()
bot = commands.Bot(command_prefix='!')

# get voice data
voice_module = vd.VoiceModule()
voice_list = vd.get_voice_list_from_local()


@bot.event
async def on_ready():
    print(f"We have logged in as {bot.user}")
    await bot.change_presence(activity=discord.Game(name="!atb_help"))


@bot.event
async def on_message(message: discord.Message):
    # ignore bot message
    if message.author == bot.user:
        return

    if message.content.startswith("!"):
        await bot.process_commands(message)
        return

    # If text start with ` or ｀, and length of text is larger than 1, and text not end with `
    if (message.content.startswith("`") or message.content.startswith("｀")) \
            and len(message.content) > 1 \
            and not message.content.endswith("`"):
        # Synthesizes the received text to speech.
        # The synthesized speech is expected to be heard on the speaker with this line executed.

        # Check bot voice channel
        bot_voice_client = await join(message)
        if not bot_voice_client:
            return

        text = message.content[1:].strip()

        if len(text) > 0:
            # Get user voice data
            user_voice_data = voice_module.get_user_data(str(message.author.id))
            default_voice_data = voice_module.get_user_data("default")

            # Check language key
            text_split_list = text.split()
            text_language_key = text.split()[0]
            has_language_key = True
            language = ""
            voice_name = ""
            if len(text_split_list) > 1:
                # Has language key, user profile
                if text_language_key in user_voice_data.voice_setting:
                    language = user_voice_data.voice_setting[text_language_key].locale
                    voice_name = user_voice_data.voice_setting[text_language_key].short_name
                    text = " ".join(text.split()[1:])
                # Has language key, no user profile
                elif text_language_key in default_voice_data.voice_setting:
                    language = default_voice_data.voice_setting[text_language_key].locale
                    voice_name = default_voice_data.voice_setting[text_language_key].short_name
                    text = " ".join(text.split()[1:])
                # No language key
                else:
                    has_language_key = False

            if not has_language_key or not len(text_split_list) > 1:
                # Language identify
                language_code = langid.classify(text)[0]

                # Has auto detected user profile
                if 'auto-' + language_code in user_voice_data.voice_setting:
                    language = user_voice_data.voice_setting['auto-' + language_code].locale
                    voice_name = user_voice_data.voice_setting['auto-' + language_code].short_name
                # No user profile but in mapping list
                elif language_code in voice_module.iso_mapping_list:
                    language = voice_module.iso_mapping_list[language_code]['Locale']
                    voice_name = voice_module.iso_mapping_list[language_code]['ShortName']
                else:
                    language = default_voice_data.voice_setting["default"].locale
                    voice_name = default_voice_data.voice_setting["default"].short_name

                print(f"Detected language: {language_code} \nVoice name       : {voice_name}")

            # SHA256
            text_sha256 = sha256(text.encode('utf-8')).hexdigest()

            # Create audio file path
            audio_file_path = f"AudioFile/{voice_name}/{text_sha256}.ogg"
            if text == "test_music":
                audio_file_path = "AudioFile/1.m4a"

            # if file doesn't exist, request for it
            if not os.path.exists(audio_file_path):
                speech_config.speech_synthesis_language = language
                speech_config.speech_synthesis_voice_name = voice_name
                speech_config.set_speech_synthesis_output_format(
                    SpeechSynthesisOutputFormat["Ogg16Khz16BitMonoOpus"])

                speech_synthesizer = speech_sdk.SpeechSynthesizer(speech_config=speech_config)

                result = speech_synthesizer.speak_text_async(text).get()

                # Checks result.
                if result.reason == speech_sdk.ResultReason.SynthesizingAudioCompleted:
                    print("Speech synthesized to speaker for text [{}]".format(text))
                elif result.reason == speech_sdk.ResultReason.Canceled:
                    cancellation_details = result.cancellation_details
                    print("Speech synthesis canceled: {}".format(cancellation_details.reason))
                    if cancellation_details.reason == speech_sdk.CancellationReason.Error:
                        if cancellation_details.error_details:
                            print("Error details: {}".format(cancellation_details.error_details))
                    print("Did you update the subscription info?")
                    return

                # If audio data doesn't exist, return
                if len(result.audio_data) < 1:
                    print("Empty audio!")
                    return

                # Save file to local
                stream = AudioDataStream(result)
                # Check folder path
                audio_folder_path = os.path.dirname(audio_file_path)
                if not os.path.exists(audio_folder_path):
                    # Create a new directory
                    os.makedirs(audio_folder_path)
                stream.save_to_wav_file(audio_file_path)
            else:
                print(f"File exist       : {text}")

            audio_source = discord.FFmpegOpusAudio(source=audio_file_path)
            # audio_source = discord.FFmpegPCMAudio(source=audio_file_path)

            while bot_voice_client.is_playing():
                await asyncio.sleep(0.5)
            bot_voice_client.play(audio_source)


@bot.event
async def on_message_edit(before, after):
    await on_message(after)


@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    pass


@bot.event
async def on_error(event):
    print(f"Error: {event}")


async def join(ctx):
    """
    Connect/move to voice channel where user is inside
    :param ctx: I have no idea what is this
    :return: bot_voice_client
    """
    # If user in voice channel
    if ctx.author.voice:
        # Get current bot voice channel
        bot_voice_client = next((voice_client for voice_client in bot.voice_clients
                                 if voice_client.guild == ctx.author.guild), None)
        user_voice = ctx.author.voice
        # If bot in a voice channel
        if bot_voice_client:
            # Move to author channel
            if not bot_voice_client.channel == user_voice.channel:
                await bot_voice_client.move_to(user_voice.channel)
        # Or join the author channel
        else:
            bot_voice_client = await user_voice.channel.connect()
    else:
        await ctx.channel.send("You are not in a voice Channel!")
        bot_voice_client = None
    return bot_voice_client


async def background_task():
    """
    Back ground task run in every 5 minutes
    """
    await bot.wait_until_ready()
    while not bot.is_closed():
        # Leave voice channel if no member in voice channel
        for voice_client in bot.voice_clients:
            if len(voice_client.channel.voice_states.keys()) < 2:
                await voice_client.disconnect()
                print("disconnected")
        await asyncio.sleep(300)


# ----------------------------------------------------Command-----------------------------------------------------------


@bot.command()
async def atb_help(ctx):
    default_voice_data = voice_module.get_user_data("default")
    default_voice_message = "\nHere is default voice setting:"
    for (key, value) in default_voice_data.voice_setting.items():
        default_voice_message += f"\n       auto-{key} : {value.short_name}"

    string = "How to use this bot:" \
             "\n        Type __`你好__ or __'Hello__" \
             "\n        Use symbol __`(text)__" \
             "\n        Bot will identify language automatically" \
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


@bot.command()
async def command(ctx):
    string = "\nCommand list:" \
             "\n`!leave`" \
             "\nLet bot leave the voice channel" \
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


@bot.command()
async def leave(ctx):
    """
    Let bot leave the voice channel
    :param ctx:
    :return:
    """
    bot_voice_client = next(
        (voice_client for voice_client in bot.voice_clients
         if voice_client.guild == ctx.author.guild), None)
    if bot_voice_client:
        await bot_voice_client.disconnect()
        await ctx.send("Voice channel left")
    else:
        await ctx.send("Not in a voice channel")


@bot.command()
async def update_voice_list(ctx):
    voice_module.voice_list = vd.get_voice_list_from_microsoft()
    await ctx.send("Done!")


@bot.command()
async def set_voice(ctx, key, voice_name):
    # Get user voice data
    user_voice_data = voice_module.get_user_data(str(ctx.author.id), False)
    if not user_voice_data.user_id:
        user_voice_data.user_id = str(ctx.author.id)
        user_voice_data.user_name = ctx.author.name

    # Search for voice data
    voice_search_data = voice_module.search(voice_name)
    if len(voice_search_data) == 1:
        # Set voice
        user_voice_data.voice_setting[key] = voice_module.search(voice_name).pop()
        # Save voice data
        voice_module.save_user_data(user_voice_data)
        await ctx.send(f"set_voice: {voice_name}")
    else:
        await ctx.send(f"Wrong voice name! : {voice_name}\n"
                       f"Use !search or visit\n"
                       f"https://docs.microsoft.com/en-us/azure/cognitive-services/speech-service/"
                       f"language-support#prebuilt-neural-voices\n"
                       f"to get correct voice name!")


@bot.command()
async def set_default_voice(ctx, key, voice_name):
    result = voice_module.set_iso_mapping_data(key, voice_name)
    await ctx.send(result)


@bot.command()
async def set_default_voice_auto(ctx):
    count_success = 0
    count_fail = 0
    for item in voice_module.iso_mapping_list.items():
        if type(item[1]) != dict:
            result = voice_module.set_iso_mapping_data(item[0], item[0] + '-', True)
            if result == 'Voice set':
                count_success += 1
            elif result == 'Wrong voice name':
                count_fail += 1
    await ctx.send(f'Done. success:{count_success} fail:{count_fail}')


@bot.command()
async def search(ctx, search_key1: str, search_key2=""):
    voice_data_search_list = voice_module.search(search_key1, search_key2)

    result = ""
    for voice_data in voice_data_search_list:
        result += f"{voice_data.short_name} {voice_data.gender} {voice_data.locale_name}\n"

    if voice_data_search_list:
        if len(result) > 2000:
            result = result[:1950] + "........\n........."
        await ctx.send(f"Search result:\n{result}")
        # else:
        #     await ctx.send(f"Too many results.\n"
        #                    f"Please change search key and try again!")
    else:
        await ctx.send(f"No data found")


@bot.command()
async def show_voice_setting(ctx):
    # Get user voice data
    user_voice_data = voice_module.get_user_data(str(ctx.author.id), False)
    if not user_voice_data.user_id:
        await ctx.send(f"User profile doesn't exist!")
    else:
        result = "Here is your voice setting\n" \
                 "---------------------------------\n"
        for (key, value) in user_voice_data.voice_setting.items():
            result += f"{key} : {value.short_name}\n"
        result += "---------------------------------\n"
        await ctx.send(f"{result}")


@bot.command()
async def delete_voice_setting(ctx, key):
    # Get user voice data
    user_voice_data = voice_module.get_user_data(str(ctx.author.id), False)
    if not user_voice_data.user_id:
        await ctx.send(f"User profile doesn't exist!")
    else:
        if key in user_voice_data.voice_setting:
            user_voice_data.voice_setting.pop(key)
            voice_module.save_user_data(user_voice_data)
            await ctx.send(f"Setting {key} deleted!")
        else:
            await ctx.send(f"Wrong key!\nPlease check your voice setting by using !show_voice_setting")


@bot.command()
async def delete_profile(ctx):
    # Get user voice data
    user_voice_data = voice_module.get_user_data(str(ctx.author.id), False)
    if not user_voice_data.user_id:
        await ctx.send(f"User profile doesn't exist!")
    else:
        voice_module.delete_user_data(user_voice_data)
        await ctx.send(f"Your profile has been deleted!")

# ----------------------------------------------------Command-----------------------------------------------------------

BOT_TOKEN = config['BOT_TOKEN']
bot.loop.create_task(background_task())
bot.run(BOT_TOKEN)
