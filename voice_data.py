import requests
import json
import os


def __get_access_token(subscription_key):
    """
    Send request get access token
    :param subscription_key: Azure TTS Api key
    :return: access_token
    """
    fetch_token_url = 'https://japaneast.api.cognitive.microsoft.com/sts/v1.0/issueToken'
    headers = {
        'Ocp-Apim-Subscription-Key': subscription_key
    }
    response = requests.post(fetch_token_url, headers=headers)
    access_token = str(response.text)
    return access_token


def __get_voice_list(subscription_key, access_token):
    """
    Send request get voice list
    :param subscription_key: Azure TTS Api key
    :param access_token: token got from __get_access_token
    :return: json formatted voice list data
    """
    url = 'https://japaneast.tts.speech.microsoft.com/cognitiveservices/voices/list'
    headers = {
        'Ocp-Apim-Subscription-Key': subscription_key,
        'Authorization': 'Bearer' + access_token
    }
    response = requests.get(url, headers=headers)
    print(response.status_code)
    voice_list = response.json()
    return voice_list


def get_voice_list_from_microsoft():
    """
    Get voice list and save file to voice_list_data.json
    :return: nothing
    """
    subscription_key = os.environ['AZURE_TTS_TOKEN']
    access_token = __get_access_token(subscription_key)
    voice_list = __get_voice_list(subscription_key, access_token)
    if voice_list:
        with open("Data/voice_list_data.json", "w") as file:
            json.dump(voice_list, file, indent=4)
    else:
        print(f"Something wrong with voice_list: {voice_list}")


class VoiceModel:
    """
    Voice model for voice list
    """
    def __init__(self, voice: dict):
        self.name = voice["Name"]
        self.displayname = voice["DisplayName"]



class UserVoiceModel:
    """
    Voice model for user
    """
    def __init__(self):
        self.default_voice = None
