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

IOS_639_1_MAPPING_LIST = {
    "zh": "zh",
    "ja": "jp",
    "ko": "kr",
    "en": "default",
    "fr": "fr",
    "th": "th"
}

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
                elif language_code in IOS_639_1_MAPPING_LIST:
                    text_language_key = IOS_639_1_MAPPING_LIST[language_code]
                    language = default_voice_data.voice_setting[text_language_key].locale
                    voice_name = default_voice_data.voice_setting[text_language_key].short_name
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


BOT_TOKEN = config['BOT_TOKEN']
bot.loop.create_task(background_task())
bot.run(BOT_TOKEN)
