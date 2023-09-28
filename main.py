import random
import voice_data as vd
import discord
from discord import app_commands
from discord.ext import commands, tasks
import os
import asyncio
import fasttext
from hashlib import sha256
import cog
from langidentification import LangIdentification
import pandas as pd
import re
from chatGPT import *
from tts import *

# Azure_TTS
speech_config = azure_init(os.environ['AZURE_TTS_TOKEN'])

# OpenAi
openai_init(os.environ['OPENAI_API_KEY'])

# get voice data
voice_module = vd.VoiceModule()
voice_list = vd.get_voice_list_from_local()

# fasttext
# PRETRAINED_MODEL_PATH_BIN = 'Data/lid.176.bin'
# fast_text_model_bin = fasttext.load_model(PRETRAINED_MODEL_PATH_BIN)
PRETRAINED_MODEL_PATH_FTZ = 'Data/lid.176.ftz'
fast_text_model_ftz = fasttext.load_model(PRETRAINED_MODEL_PATH_FTZ)

# langidentification
# langid_model = LangIdentification(model_type='augmented')

# get dic
DIC_TEXT_SHA256_LANGUAGE_CODE_PATH = "Data/dic_text_sha256_language_code.pickle"
try:
    dic_text_sha256_language_code = pd.read_pickle(DIC_TEXT_SHA256_LANGUAGE_CODE_PATH)
except Exception:
    dic_text_sha256_language_code = {}

# Discord
intents = discord.Intents.all()
client = discord.Client(command_prefix='!', intents=intents)
tree = app_commands.CommandTree(client)


@client.event
async def on_ready():
    print(f"We have logged in as {client.user}")
    # await client.add_cog(cog.Cog(client, voice_module))
    # await client.change_presence(activity=discord.Game(name="!atb_help"))
    background_task.start()
    try:
        synced = await tree.sync()
        print(f'Synced {len(synced)} command(s)')
    except Exception as e:
        print(e)
    print(f"Ready!")


@tree.command(name='miel_bot')
@app_commands.describe(question='What would you want to ask Miel?')
async def miel_bot(interaction: discord.Interaction, question: str):
    #await interaction.response.defer()
    #message = await interaction.followup.send(f'{interaction.user.name} said:{thing_to_say}')
    #await message.reply('test')
    reply_list = ['草', '哈哈哈哈哈哈', '是的', '他妈的']
    await interaction.response.send_message(f'Q: {question}\n'
                                            f'Miel: {random.choice(reply_list)}')


@tree.command(name='chat')
@app_commands.describe(prompt='Just ask anything!',
                       model='Default or 0: gpt-3.5-turbo.'
                             '1: text-davinci-003',
                       show_all_response='Default: False',
                       temperature='Only works for davinci. Default: 0.5',
                       max_tokens='Only works for davinci. Default: 1000',)
async def chat(interaction: discord.Interaction,
               prompt: str,
               model: int = 0,
               temperature: float = 0.5,
               max_tokens: int = 1000,
               show_all_response: bool = False):
    await interaction.response.defer()
    if model == 1:
        response = await request_chatgpt_v1(prompt, 'text-davinci-003', temperature, max_tokens, show_all_response)
    else:
        response = await request_chatgpt_v2(prompt, 'gpt-3.5-turbo', show_all_response)
    max_len = 1950
    if len(response) < max_len:
        await interaction.followup.send(f'Q: {prompt}\nA: {response}')
    else:
        message = await interaction.followup.send(f'Q: {prompt}\nA: {response[:max_len-len(prompt)]}')
        for i in range(max_len - len(prompt), len(response), max_len):
            message = await message.reply(response[i:i+max_len])


@client.event
async def on_message(message: discord.Message):
    # ignore client message
    if message.author == client.user:
        return

    # text must start with ` or ｀, and length of text is larger than 1
    if not re.search(r'^(`|｀)[^`｀]+$', message.content):
        return

    # Check client voice channel
    bot_voice_client = await join(message)
    if not bot_voice_client:
        return

    # remove [`]
    text = message.content[1:].strip()

    # Get user voice data
    user_voice_data = voice_module.get_user_data(str(message.author.id))
    # default_voice_data = voice_module.get_user_data("default")

    # Check language key
    text_split_list = text.split()
    text_language_key = text_split_list[0]
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
            # fast_text_result = fast_text_model_bin.predict(text)
            fast_text_result = fast_text_model_ftz.predict(text)
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
        result = get_audio(language, voice_name, text, speech_config)

        if result is None:
            await message.channel.send("Something's wrong! <@318760182144434176>")
            return

        # If audio data doesn't exist, try detect language with other module and try again
        if len(result.audio_data) < 1:
            return
            print(f"Empty audio!")
            print("Detect language again")

            # language detection
            lang_id_result = langid_model.predict_lang(text)
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


@client.event
async def on_message_edit(before, after):
    await on_message(after)


@client.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    pass


@client.event
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
        # Get current client voice channel
        bot_voice_client = next((voice_client for voice_client in client.voice_clients
                                 if voice_client.guild == ctx.author.guild), None)
        user_voice = ctx.author.voice
        # If client in a voice channel
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


@tasks.loop(seconds=60)
async def background_task():
    """
    Back ground task run in every 5 minutes
    """
    await client.wait_until_ready()
    while not client.is_closed():
        # Leave voice channel if no member in voice channel
        for voice_client in client.voice_clients:
            if len(voice_client.channel.voice_states.keys()) < 2:
                await voice_client.disconnect()
                print("disconnected")
        await asyncio.sleep(300)


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


BOT_TOKEN = os.environ['BOT_TOKEN']
client.run(BOT_TOKEN)
