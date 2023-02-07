import re

import voice_data as vd
import discord
from discord.ext import commands
import os
import azure.cognitiveservices.speech as speech_sdk
from azure.cognitiveservices.speech import AudioDataStream, SpeechSynthesisOutputFormat
import asyncio
import yaml
import fasttext
from hashlib import sha256
import cog
import langid
import pandas as pd
import openai
import re

# Load config
with open('config.yml', 'r') as yml:
    config = yaml.safe_load(yml)

# Azure_TTS
# Creates an instance of a speech config with specified subscription key and service region.
AZURE_TTS_TOKEN = config['AZURE_TTS_TOKEN']
speech_key, service_region = AZURE_TTS_TOKEN, 'japaneast'
speech_config = speech_sdk.SpeechConfig(subscription=speech_key, region=service_region)
openai.api_key = config['OPENAI_API_KEY']

# discord
bot = commands.Bot(command_prefix='!')

# get voice data
voice_module = vd.VoiceModule()
voice_list = vd.get_voice_list_from_local()

# fasttext
PRETRAINED_MODEL_PATH_BIN = 'Data/lid.176.bin'
fast_text_model_bin = fasttext.load_model(PRETRAINED_MODEL_PATH_BIN)
PRETRAINED_MODEL_PATH_FTZ = 'Data/lid.176.ftz'
fast_text_model_ftz = fasttext.load_model(PRETRAINED_MODEL_PATH_FTZ)

# get dic
DIC_TEXT_SHA256_LANGUAGE_CODE_PATH = "Data/dic_text_sha256_language_code.pickle"
try:
    dic_text_sha256_language_code = pd.read_pickle(DIC_TEXT_SHA256_LANGUAGE_CODE_PATH)
except Exception:
    dic_text_sha256_language_code = {}


@bot.event
async def on_ready():
    print(f"We have logged in as {bot.user}")
    bot.add_cog(cog.Cog(bot, voice_module))
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

        if len(text) == 0:
            return

        # Get user voice data
        user_voice_data = voice_module.get_user_data(str(message.author.id))
        # default_voice_data = voice_module.get_user_data("default")

        # Check language key
        text_split_list = text.split()
        text_language_key = text.split()[0]
        has_language_key = True
        language = ""
        voice_name = ""
        if len(text_split_list) > 1:
            # Has language key, has user profile
            if text_language_key in user_voice_data.voice_setting:
                language = user_voice_data.voice_setting[text_language_key].locale
                voice_name = user_voice_data.voice_setting[text_language_key].short_name
                text = " ".join(text.split()[1:])
            # Has language key, no user profile
            elif text_language_key in voice_module.iso_mapping_list:
                language = voice_module.iso_mapping_list[text_language_key]['Locale']
                voice_name = voice_module.iso_mapping_list[text_language_key]['ShortName']
                text = " ".join(text.split()[1:])
            # No language key
            else:
                has_language_key = False

        # SHA256
        text_sha256 = sha256(text.encode('utf-8')).hexdigest()

        if not has_language_key or not len(text_split_list) > 1:
            if text_sha256 in dic_text_sha256_language_code:
                language_code = dic_text_sha256_language_code[text_sha256]
                print("Found language key in cache")
            else:
                # Language detect
                fast_text_result = fast_text_model_bin.predict(text)
                fast_text_result2 = fast_text_model_ftz.predict(text)
                language_code = fast_text_result[0][0].split('_')[-1]

            language, voice_name = get_voice_name(user_voice_data, language_code)

            print(f"Detected language: {language_code} \nVoice name       : {voice_name}")
        else:
            print(f"Language key     : {text_language_key} \nVoice name       : {voice_name}")

        # Create audio file path
        audio_file_path = f"AudioFile/{voice_name}/{text_sha256}.ogg"
        if text == "test_music":
            audio_file_path = "AudioFile/1.m4a"

        # if file doesn't exist, request for it
        if not os.path.exists(audio_file_path):
            # get audio file
            result = get_audio(language, voice_name, text)

            if result is None:
                await message.channel.send("Something's wrong! <@318760182144434176>")
                return

            # If audio data doesn't exist, try detect language with other module and try again
            if len(result.audio_data) < 1:
                print(f"Empty audio!")
                print("Detect language again")

                # language detection
                lang_id_result = langid.classify(text)
                language, voice_name = get_voice_name(user_voice_data, lang_id_result[0])
                print(f"Detected language: {lang_id_result[0]} \nVoice name       : {voice_name}")

                # get audio file again
                result = get_audio(language, voice_name, text)
                if result is None:
                    await message.channel.send("Something's wrong! <@318760182144434176>")
                    return

                if len(result.audio_data) < 1:
                    await message.channel.send(f'Failed to get audio ㅠㅠ\nOriginal message : {text}')
                    return

                audio_file_path = f"AudioFile/{voice_name}/{text_sha256}.ogg"

                # Save sha256 and language code
                dic_text_sha256_language_code[text_sha256] = language_code
                pd.to_pickle(dic_text_sha256_language_code, DIC_TEXT_SHA256_LANGUAGE_CODE_PATH)

            # Save file to local
            stream = AudioDataStream(result)
            # Check folder path
            audio_folder_path = os.path.dirname(audio_file_path)
            if not os.path.exists(audio_folder_path):
                # Create a new directory
                os.makedirs(audio_folder_path)
            stream.save_to_wav_file(audio_file_path)
        else:
            print(f"File exist       : [{text}]")

        audio_source = discord.FFmpegOpusAudio(source=audio_file_path)
        # audio_source = discord.FFmpegPCMAudio(source=audio_file_path)

        while bot_voice_client.is_playing():
            await asyncio.sleep(0.5)
        bot_voice_client.play(audio_source)
    elif message.content.startswith('/chat '):
        split = message.content[6:].strip().split('-')
        prompt = split[0].strip()
        temperature = 0
        max_tokens = 1000

        for arg in split[1:]:
            match = re.search(r'^(temperature|t) (0|1|0.\d\d?) ?$', arg, re.IGNORECASE)
            if match:
                temperature = float(match.group(2))
                continue

            match = re.search(r'^(max_token|m_t) ([1-9]\d*) ?$', arg, re.IGNORECASE)
            if match:
                max_tokens = int(match.group(2))

        bot_message = await message.reply("Getting response...")

        try:
            response = openai.Completion.create(model="text-davinci-003",
                                                prompt=prompt,
                                                temperature=temperature,
                                                max_tokens=max_tokens)

            # await message.edit(content=response)
            await bot_message.edit(content=response['choices'][0].text)
        except Exception as e:
            await bot_message.edit(content=f"error:{e}")

@bot.event
async def on_message_edit(before, after):
    await on_message(after)


@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    pass


@bot.event
async def on_error(event_name, *args, **kwargs):
    print(f"Error: {event_name}, {args}, {kwargs}")


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


def get_audio(language: str, voice_name: str, text: str):
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
        return None
    return result


def get_voice_name(user_voice_data, language_code):
    # Has auto detected user profile
    if 'auto-' + language_code in user_voice_data.voice_setting:
        language = user_voice_data.voice_setting['auto-' + language_code].locale
        voice_name = user_voice_data.voice_setting['auto-' + language_code].short_name
    # No user profile but in mapping list
    elif language_code in voice_module.iso_mapping_list:
        language = voice_module.iso_mapping_list[language_code]['Locale']
        voice_name = voice_module.iso_mapping_list[language_code]['ShortName']
    else:
        language = voice_module.iso_mapping_list['en']['Locale']
        voice_name = voice_module.iso_mapping_list['en']['ShortName']
    return language, voice_name


BOT_TOKEN = config['BOT_TOKEN']
bot.loop.create_task(background_task())
bot.run(BOT_TOKEN)
