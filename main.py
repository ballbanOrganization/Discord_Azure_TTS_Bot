import discord
import os
import azure.cognitiveservices.speech as speechsdk
from azure.cognitiveservices.speech import AudioDataStream
from azure.cognitiveservices.speech.audio import AudioOutputConfig

# Azure_TTS
# Creates an instance of a speech config with specified subscription key and service region.
AZURE_TTS_TOKEN = os.environ['AZURE_TTS_TOKEN']
speech_key, service_region = AZURE_TTS_TOKEN, "japaneast"
speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=service_region)

# discord
BOT_TOKEN = os.environ['BOT_TOKEN']
bot = discord.Client()


@bot.event
async def on_ready():
    print(f"We have logged in as {bot.user}")


@bot.event
async def on_message(message: discord.Message):
    # ignore bot message
    if message.author == bot.user:
        return

    if message.content.startswith(f"`"):
        # Synthesizes the received text to speech.
        # The synthesized speech is expected to be heard on the speaker with this line executed.
        text = message.content[1:].lower()
        if len(text) > 0:
            if text.startswith("en"):
                language = "en-US"
                voice_name = "en-US-JennyNeural"
                text = " ".join(text.split()[1:])
            elif text.startswith("jp"):
                language = "ja-JP"
                voice_name = "ja-JP-KeitaNeural"
                text = " ".join(text.split()[1:])
            elif text.startswith("kr"):
                language = "ja-JP"
                voice_name = "ko-KR-SunHiNeural"
                text = " ".join(text.split()[1:])
            elif text.startswith("hk"):
                language = "zh-HK"
                voice_name = "zh-HK-WanLungNeural"
                text = " ".join(text.split()[1:])
            elif text.startswith("tw"):
                language = "zh-TW"
                voice_name = "zh-TW-HsiaoChenNeural"
                text = " ".join(text.split()[1:])
            else:
                # text.startswith("chinese") or text.startswith("cn"):
                language = "zh-CN"
                voice_name = "zh-CN-XiaoxiaoNeural"

            speech_config.speech_synthesis_language = language
            speech_config.speech_synthesis_voice_name = voice_name

            audio_file_path = f"AudioFile/{text}_{voice_name}.wav"

            # if file doesn't exist, request for it
            if not os.path.exists(audio_file_path):
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

                # Save file to local
                stream = AudioDataStream(result)
                stream.save_to_wav_file(audio_file_path)

            # Check bot voice channel
            bot_voice_client = \
                next((voice_client for voice_client in bot.voice_clients
                      if voice_client.guild == message.author.guild), None)
            await join(message, bot_voice_client)
            bot_voice_client = \
                next((voice_client for voice_client in bot.voice_clients
                      if voice_client.guild == message.author.guild), None)

            # audio_source = discord.PCMAudio(stream)
            audio_source = discord.FFmpegPCMAudio(source=audio_file_path)

            bot_voice_client.play(audio_source)

            # Send discord message
            # await message.channel.send(f"{text}")


async def join(ctx, bot_voice_client):
    """
    Connect/move to voice channel where user is inside
    :param ctx: I have no idea what is this
    :param bot_voice_client: bot voice client
    :return: nothing
    """
    if ctx.author.voice:
        user_voice = ctx.author.voice
        # if bot in a voice channel
        if bot_voice_client:
            # if in same voice channel with author
            if bot_voice_client.channel == user_voice.channel:
                return
            # Or move to author channel
            else:
                await bot_voice_client.move_to(user_voice.channel)
        # Or join the author channel
        else:
            await user_voice.channel.connect()
    else:
        await ctx.channel.send("You are not in a voice Channel!")


async def leave(ctx):
    """
    Let bot leave the voice channel
    :param ctx:
    :return:
    """
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("Voice channel left")
    else:
        await ctx.send("Not in a voice channel")

bot.run(BOT_TOKEN)
