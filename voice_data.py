import requests
import json
import os

VOICE_LIST_DATA_PATH = "Data/voice_list_data.json"
USER_DATA_PATH = "Data/user_data.json"
ISO639_MAPPING_LIST = "Data/ISO639-1_mapping_list.json"


class VoiceModel:
    """
    Voice model for voice list
    """
    def __init__(self, voice: dict):
        self.data_raw = voice
        self.name = voice["Name"]
        self.display_name = voice["DisplayName"]
        self.local_name = voice["LocalName"]
        self.short_name = voice["ShortName"]
        self.gender = voice["Gender"]
        self.locale = voice["Locale"]
        self.locale_name = voice["LocaleName"]
        self.sample_rate_hertz = voice["SampleRateHertz"]
        self.voice_type = voice["VoiceType"]
        self.status = voice["Status"]
        self.style_list = voice["StyleList"] if "StyleList" in voice else None
        self.role_play_list = voice[
            "RolePlayList"] if "RolePlayList" in voice else None

    def to_json(self):
        dic = {"Name": self.name,
               "DisplayName": self.display_name,
               "LocalName": self.local_name,
               "ShortName": self.short_name,
               "Gender": self.gender,
               "Locale": self.locale,
               "LocaleName": self.locale_name,
               "SampleRateHertz": self.sample_rate_hertz,
               "VoiceType": self.voice_type,
               "Status": self.status}
        if self.style_list:
            dic["StyleList"] = self.style_list
        if self.role_play_list:
            dic["RolePlayList"] = self.role_play_list
        return dic


class UserModel:
    """
    Model for user
    """
    def __init__(self, user_data):
        if user_data:
            self.data_raw = user_data
            self.user_id = user_data["UserId"]
            self.user_name = user_data["UserName"] if "UserName" in user_data else None
            self.voice_setting = {key: VoiceModel(value) for (key, value) in user_data["VoiceSetting"].items()}
        else:
            self.data_raw = None
            self.user_id = None
            self.user_name = None
            self.voice_setting = {}

    def to_json(self):
        dic = {
            "UserId": self.user_id,
            "UserName": self.user_name,
            "VoiceSetting": {key: value.to_json() for (key, value) in self.voice_setting.items()}
        }
        return dic


def __get_access_token(subscription_key):
    """
    Send request get access token
    :param subscription_key: Azure TTS Api key
    :return: access_token
    """
    fetch_token_url = 'https://japaneast.api.cognitive.microsoft.com/sts/v1.0/issueToken'
    headers = {'Ocp-Apim-Subscription-Key': subscription_key}
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


def get_user_data_list():
    """
    Get user data list from USER_DATA_PATH
    :return: User data list
    """
    try:
        with open(USER_DATA_PATH, "r") as file:
            user_data_list = json.load(file)
    except FileExistsError:
        user_data_list = get_voice_list_from_microsoft()
    return user_data_list


def get_voice_list_from_local():
    """
    Get voice list from voice_list_data.json
    :return: voice_list
    """
    with open(VOICE_LIST_DATA_PATH, "r") as file:
        voice_list = json.load(file)
    return voice_list


def get_voice_list_from_microsoft():
    """
    Get voice list and save file to voice_list_data.json
    :return: voice_list
    """
    subscription_key = os.environ['AZURE_TTS_TOKEN']
    access_token = __get_access_token(subscription_key)
    voice_list = __get_voice_list(subscription_key, access_token)
    if voice_list:
        with open(VOICE_LIST_DATA_PATH, "w") as file:
            json.dump(voice_list, file, indent=4)
        return voice_list
    else:
        print(f"Something wrong with voice_list: {voice_list}")


def get_iso_mapping_list():
    try:
        with open(ISO639_MAPPING_LIST, "r") as file:
            iso_list = json.load(file)
    except FileExistsError:
        return {}
    return iso_list


class VoiceModule:
    def __init__(self):
        self.voice_list = get_voice_list_from_local()
        self.user_data_list = get_user_data_list()
        self.iso_mapping_list = get_iso_mapping_list()

    def save_user_data(self, user_model: UserModel):
        """
        Save user data setting to local file
        :param user_model: User model
        :return: nothing
        """
        if str(user_model.user_id) in self.user_data_list:
            self.user_data_list[str(user_model.user_id)].update(user_model.to_json())
        else:
            self.user_data_list[str(user_model.user_id)] = user_model.to_json()
        with open(USER_DATA_PATH, "w") as file:
            json.dump(self.user_data_list, file, indent=4)

    def delete_user_data(self, user_model: UserModel):
        """
        Delete user data setting
        :param user_model: User model
        :return: nothing
        """
        self.user_data_list.pop(str(user_model.user_id))
        with open(USER_DATA_PATH, "w") as file:
            json.dump(self.user_data_list, file, indent=4)

    def get_user_data(self, user_id: str, default=True):
        """
        Get user data by user id
        :param user_id: User id from discord
        :param default: Get default user if user id doesn't exist
        :return: UserModel or None
        """
        if user_id in self.user_data_list:
            user_data = self.user_data_list[user_id]
        elif default:
            user_data = self.user_data_list["default"]
        else:
            user_data = None
        return UserModel(user_data)

    def search(self, search_key1: str, search_key2=""):
        """
        Search and return every voice data which contains search_key1 and search_key2
        :param search_key1: search_key1
        :param search_key2: search_key2
        :return: VoiceModel list
        """
        result = [
            VoiceModel(voice) for voice in self.voice_list if len({
                value
                for (key, value) in voice.items()
                if type(value) == str and value.lower().find(search_key1.lower()) >= 0
            }) > 0
        ]
        if search_key2:
            result = [
                x for x in result if len({
                    value
                    for (key, value) in x.data_raw.items()
                    if type(value) == str and value.lower().find(search_key2.lower()) >= 0
                }) > 0
            ]
        return result

    def set_iso_mapping_data(self, key, voice_name, set_first=False):
        """
        Set iso mapping data
        :param key: iso key
        :param voice_name: voice name
        :param set_first: option for choose first voice or not
        :return:
        """
        search_list = self.search(voice_name)
        if len(search_list) > 0:
            if len(search_list) == 1 or set_first:
                self.iso_mapping_list[key] = search_list[0].to_json()
                with open(ISO639_MAPPING_LIST, "w") as file:
                    json.dump(self.iso_mapping_list, file, indent=4)
                return 'Voice set'
            else:
                return 'Wrong voice name'
        else:
            return 'Wrong voice name'
