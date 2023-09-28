import azure.cognitiveservices.speech as speech_sdk
from azure.cognitiveservices.speech import AudioDataStream, SpeechSynthesisOutputFormat


def azure_init(key):
    # Creates an instance of a speech config with specified subscription key and service region.
    speech_key, service_region = key, 'japaneast'
    return speech_sdk.SpeechConfig(subscription=speech_key, region=service_region)


def get_audio(language: str, voice_name: str, text: str, speech_config):
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
