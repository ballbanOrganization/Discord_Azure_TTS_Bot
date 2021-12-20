import discord
from discord.ext import commands
import os
import azure.cognitiveservices.speech as speechsdk
from azure.cognitiveservices.speech import AudioDataStream, SpeechSynthesisOutputFormat
import voice_data
import re

SINGLE_COMMAND_LIST = ['update_voice_list', 'leave', 'l', 'help', 'h']
COMMAND_LIST = ['set_voice', 'set_default_voice']

# Azure_TTS
# Creates an instance of a speech config with specified subscription key and service region.
AZURE_TTS_TOKEN = os.environ['AZURE_TTS_TOKEN']
speech_key, service_region = AZURE_TTS_TOKEN, "japaneast"
speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=service_region)

# discord
bot = discord.Client()
bot = commands.Bot(command_prefix='`')


@bot.command()
async def set_voice(ctx, voice_name):
    await ctx.send(f"set_voice: {voice_name}")


@bot.command()
async def set_default_voice(ctx, voice_name):
    await ctx.send(f"set_default_voice: {voice_name}")


@bot.command()
async def update_voice_list(ctx):
    voice_data.get_voice_list_from_microsoft()
    await ctx.send("Done!")


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


@bot.event
async def on_ready():
    print(f"We have logged in as {bot.user}")


@bot.event
async def on_message(message: discord.Message):
    # ignore bot message
    if message.author == bot.user:
        return

    if (message.content.startswith(f"`") or message.content.startswith(f"｀")) and len(message.content) > 1:
        # Synthesizes the received text to speech.
        # The synthesized speech is expected to be heard on the speaker with this line executed.

        # Check command
        temp_list = message.content[1:].split()
        if temp_list[0] in COMMAND_LIST:
            await bot.process_commands(message)
            return

        # Check bot voice channel
        bot_voice_client = next(
            (voice_client for voice_client in bot.voice_clients
             if voice_client.guild == message.author.guild), None)
        if await join(message, bot_voice_client):
            bot_voice_client = next(
                (voice_client for voice_client in bot.voice_clients
                 if voice_client.guild == message.author.guild), None)

            # Replace invalid symbol
            text = re.sub('[<>/|":*]', ' ', message.content[1:])
            text = text.replace("\\", " ")

            if len(text) > 0:
                if text.startswith('en'):
                    language = 'en-US'
                    voice_name = 'en-US-JennyNeural'
                    text = ' '.join(text.split()[1:])
                elif text.startswith('jp'):
                    language = 'ja-JP'
                    voice_name = 'ja-JP-KeitaNeural'
                    text = ' '.join(text.split()[1:])
                elif text.startswith('kr'):
                    language = 'ja-JP'
                    voice_name = 'ko-KR-SunHiNeural'
                    text = ' '.join(text.split()[1:])
                elif text.startswith("hk"):
                    language = "zh-HK"
                    voice_name = 'zh-HK-WanLungNeural'
                    text = ' '.join(text.split()[1:])
                elif text.startswith('tw'):
                    language = 'zh-TW'
                    voice_name = 'zh-TW-HsiaoChenNeural'
                    text = ' '.join(text.split()[1:])
                else:
                    # text.startswith("chinese") or text.startswith("cn"):
                    language = 'zh-CN'
                    voice_name = 'zh-CN-XiaoxiaoNeural'

                audio_file_path = f"AudioFile/{voice_name}/{text}.ogg"
                if text == "test_music":
                    audio_file_path = "AudioFile/1.m4a"

                # if file doesn't exist, request for it
                if not os.path.exists(audio_file_path):
                    speech_config.speech_synthesis_language = language
                    speech_config.speech_synthesis_voice_name = voice_name
                    speech_config.set_speech_synthesis_output_format(
                        SpeechSynthesisOutputFormat["Ogg16Khz16BitMonoOpus"])

                    speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config)

                    result = speech_synthesizer.speak_text_async(text).get()

                    # Checks result.
                    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                        print("Speech synthesized to speaker for text [{}]".format(text))
                    elif result.reason == speechsdk.ResultReason.Canceled:
                        cancellation_details = result.cancellation_details
                        print("Speech synthesis canceled: {}".format(cancellation_details.reason))
                        if cancellation_details.reason == speechsdk.CancellationReason.Error:
                            if cancellation_details.error_details:
                                print("Error details: {}".format(cancellation_details.error_details))
                        print("Did you update the subscription info?")

                    # Change <?> to ASCII before save
                    audio_file_path = audio_file_path.replace('?', '&#63;')

                    # Save file to local
                    stream = AudioDataStream(result)
                    # Check folder path
                    audio_folder_path = os.path.dirname(audio_file_path)
                    if not os.path.exists(audio_folder_path):
                        # Create a new directory
                        os.makedirs(audio_folder_path)
                    stream.save_to_wav_file(audio_file_path)

                # Change <?> to ASCII before load
                audio_file_path = audio_file_path.replace('?', '&#63;')

                audio_source = discord.FFmpegOpusAudio(source=audio_file_path)
                # audio_source = discord.FFmpegPCMAudio(source=audio_file_path)

                bot_voice_client.play(audio_source)

                # Send discord message
                # await message.channel.send(f"{text}")


async def join(ctx, bot_voice_client):
    """
    Connect/move to voice channel where user is inside
    :param ctx: I have no idea what is this
    :param bot_voice_client: bot voice client
    :return: bool
    """
    join_check = True
    if ctx.author.voice:
        user_voice = ctx.author.voice
        # If bot in a voice channel
        if bot_voice_client:
            # Move to author channel
            if not bot_voice_client.channel == user_voice.channel:
                await bot_voice_client.move_to(user_voice.channel)
        # Or join the author channel
        else:
            await user_voice.channel.connect()
    else:
        await ctx.channel.send("You are not in a voice Channel!")
        join_check = False
    return join_check


BOT_TOKEN = os.environ['BOT_TOKEN']
bot.run(BOT_TOKEN)
