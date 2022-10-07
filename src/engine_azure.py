# NOT active
# Run: GOOGLE_APPLICATION_CREDENTIALS=/Users/bing.wu/.ssh/personal_gcp_svc_acct.json gcloud auth application-default print-access-token | pbcopy
import json
import logging
import ntpath
import os
from pprint import pprint

import requests

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class AzureBob(object):
    def __init__(self, app_config: dict):
        self.app_config = app_config
        self.api_key = self._get_key_val('speech_key')
        self.region = 'eastus'

    def _get_key_val(self, key: str, def_val: str = None) -> str:
        val = self.app_config['azure'].get(key, None) or os.getenv(key.upper(), None) or def_val
        assert val, f"Missing key/value for '{key}'"
        return val or def_val

    def get_voices(self):
        url = f'https://{self.region}.customvoice.api.speech.microsoft.com/api/texttospeech/v3.0/longaudiosynthesis/voices'
        header = {
            'Ocp-Apim-Subscription-Key': self.api_key
        }
        response = requests.get(url, headers=header)
        print(response.text)

    def convert(self, src_txt: str) -> bool:
        region = 'eastus'
        key = self.api_key
        input_file_path = '/tmp/npr_test2.extracted.txt'
        locale = 'en-US'
        voice_name = 'en-US-JennyNeural'
        output_format = 'audio-16khz-32kbitrate-mono-mp3'
        url = f'https://{region}.customvoice.api.speech.microsoft.com/api/texttospeech/v3.0/longaudiosynthesis'
        header = {
            'Ocp-Apim-Subscription-Key': key
        }

        voice_identities = [
            {
                'voicename': voice_name
            }
        ]

        payload = {
            'displayname': 'my audio synthesis sample',
            'description': 'My description',
            'locale': locale,
            'voices': json.dumps(voice_identities),
            'outputformat': output_format,
            'concatenateresult': True,
        }

        filename = ntpath.basename(input_file_path)
        files = {
            'script': (filename, open(input_file_path, 'rb'), 'text/plain')
        }

        response = requests.post(url, payload, headers=header, files=files)
        pprint(response)
        print('response.status_code: %d' % response.status_code)
        print(response.headers['Location'])
        return True


if __name__ == '__main__':
    inst = AzureBob(app_config={'azure': {}})
    inst.get_voices()
    # inst.convert(src_txt='')
