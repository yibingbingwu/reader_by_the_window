import json
import logging
import ntpath
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from pprint import pformat
from typing import Optional, Tuple, Dict

import requests

from src.engine_azure import AzureBob

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class AzureBobAsync(AzureBob):

    # Need to pick the right Speech_Key
    def convert_long(self, src_fn: str) -> bool:
        url = f'https://{self.region}.customvoice.api.speech.microsoft.com/api/texttospeech/v3.0/longaudiosynthesis'
        voice_identities = [
            {
                'voicename': self.voice_name
            }
        ]

        tz = datetime.now(timezone.utc).astimezone().tzinfo
        dstr = datetime.now().strftime(f"%Y-%m-%dT%H:%M:%S {tz}")
        theme = self.app_config.get('invocation-theme-word') or 'UNDEFINED'
        payload = {
            'displayname': f'long_audio_task_for_{theme}',
            'description': f'Theme={theme}, Voice={self.voice_name}, Time={dstr}',
            'locale': self.locale,
            'voices': json.dumps(voice_identities),
            'outputformat': self.audio_format,
            'concatenateresult': True,
        }

        filename = ntpath.basename(src_fn)
        files = {
            'script': (filename, open(src_fn, 'rb'), 'text/plain')
        }

        logger.debug("Submitting a new async synthesize task ...")
        response = requests.post(url, payload, headers=self.header, files=files)
        if response.status_code not in [200, 202]:
            raise RuntimeError(f"Azure call to {url} failed. "
                               "See response for details\n" + pformat(response.reason, indent=2))
        ask_endpt = response.headers['Location']
        logger.debug(f"Remote endpoint replied with an inquery endpoint {ask_endpt}")

        last_resp_dict = {}
        for cnt in range(60):
            local_fn, last_resp_dict = self.wait_and_check(wait_for_sec=30, query_endpoint=ask_endpt)
            if local_fn:
                logger.info(f'Successfully downloaded file to {local_fn}')
                return True

        logger.info(f"""Timeout waiting for the Synthesize task to complete. 
You will have to manually download the output file. Here are the artifacts:
- Task ID = {last_resp_dict.get('id')}
- Last status = {last_resp_dict.get('status')}
- Inquire endpoint = {ask_endpt}
""")

        return True

    def wait_and_check(self, wait_for_sec: int, query_endpoint: str) -> Tuple[Optional[str], Dict]:
        logger.debug(f"Waiting for {wait_for_sec} seconds ...")
        time.sleep(wait_for_sec)
        response = requests.get(query_endpoint, headers=self.header)
        if response.status_code not in [200, 202]:
            raise RuntimeError(f"Azure call to {query_endpoint} failed. "
                               "See response for details\n" + pformat(response.reason, indent=2))

        resp_dict = json.loads(response.text)
        task_id = resp_dict.get('id')
        status = resp_dict.get('status').upper()
        assert task_id and status, f'Unexpected response from {query_endpoint}: cannot find key "id" and/or "status"'
        logger.debug(f"Latest status is {status}")

        if status in ['NOTSTARTED', 'RUNNING']:
            return None, resp_dict

        if status == 'FAILED':
            raise RuntimeError(f"Azure Task id={task_id} failed. "
                               "See response for details\n{response.text}")

        if status == 'SUCCEEDED':
            url = f'https://{self.region}.customvoice.api.speech.microsoft.com/api/texttospeech/v3.0/longaudiosynthesis/{task_id}/files'
            response = requests.get(url, headers=self.header)
            if response.status_code not in [200, 202]:
                raise RuntimeError(f"Azure call to {url} failed. "
                                   "See response for details\n" + pformat(response.reason, indent=2))

            result_dict = json.loads(response.text)
            # logger.debug(f'Result is contained in this replay: \n{response.text}\n')

            for v in result_dict['values']:
                if v['kind'] != 'LongAudioSynthesisResult':
                    continue

                result_url = v['links']['contentUrl']
                logger.debug(f'Result is can be downloaded from "{result_url}"')

                local_fn = self.app_config['output_audio_fn']
                local_fn = local_fn[:-3] + 'zip'
                Path(os.path.realpath(os.path.dirname(local_fn))).mkdir(parents=True, exist_ok=True)
                if os.path.exists(local_fn):
                    os.remove(local_fn)

                response = requests.get(result_url)
                open(local_fn, "wb").write(response.content)

                return local_fn, resp_dict

        return None, resp_dict


# if __name__ == '__main__':
#     eng_test_basic()
