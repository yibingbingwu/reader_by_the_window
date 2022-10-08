import html
import json
import logging
import ntpath
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from pprint import pformat
from typing import Optional, Tuple, Dict

import azure.cognitiveservices.speech as speechsdk
import requests

from engine_base import VoiceEngine

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class AzureBob(VoiceEngine):
    locale_mapping = {
        'english': ('zh-US', ['en-US-MichelleNeural', 'en-US-EricNeural']),
        'chinese-普通': ('zh-CN', ['zh-CN-YunfengNeural']),
        'chinese-四川': ('zh-CN-sichuan', ['zh-CN-sichuan-YunxiNeural']),
        'chinese-东北': ('zh-CN-liaoning', ['zh-CN-liaoning-XiaobeiNeural']),
        'chinese-山东': ('zh-CN-shandong', ['zh-CN-shandong-YunxiangNeural']),
        'chinese-台湾': ('zh-TW', ['zh-TW-HsiaoChenNeural']),
        'chinese-广东': ('zh-HK', ['zh-HK-WanLungNeural']),
        'chinese-河南': ('zh-CN-henan', ['zh-CN-henan-YundengNeural']),
        'chinese-陕西': ('zh-CN-shaanxi', ['zh-CN-shaanxi-XiaoniNeural']),
    }

    def _resolve_locale_voice(self):
        lang = self.app_config['lang']
        mapping = AzureBob.locale_mapping.get(lang)
        self.locale = self.app_config['azure'].get('locale')
        if self.locale:
            assert self.locale == mapping[0], "The 'locale' property in the configuration file does not " \
                                              "match internally defined allowed values. " \
                                              "Please double check and run again"
        else:
            self.locale = mapping[0]

        self.voice_name = self.app_config['azure'].get('voice_name')
        if self.voice_name:
            assert self.voice_name in mapping[1], "The 'voice_name' property in the configuration file does not " \
                                                  "match internally defined allowed values. " \
                                                  "Please double check and run again"
        else:
            self.voice_name = mapping[1][0]

    def _calc_tone_change(self):
        if self.app_config[self.eng].get('speed'):
            self.rate = '{:+.2f}%'.format((float(self.app_config[self.eng]['speed']) - 1) * 100)
        else:
            self.rate = "-0.00%"

        if self.app_config[self.eng].get('pitch'):
            self.pitch = '{:+.2f}%'.format((float(self.app_config[self.eng]['pitch']) - 1) * 100)
        else:
            self.pitch = "-0.00%"

    def __init__(self, app_config: dict):
        super().__init__(app_config, 'azure')

        self.app_config = app_config
        self.region = self.app_config.get('region') or 'eastus'
        self.api_key = self._get_key_val('speech_key')
        self.audio_format = self._get_key_val('audio_format', 'audio-16khz-32kbitrate-mono-mp3')
        self.header = {
            'Ocp-Apim-Subscription-Key': self.api_key
        }
        self._resolve_locale_voice()

    def get_voices(self):
        # Display as plain text what the Voice Names are available for the Speech Resource represented by this key
        url = f'https://{self.region}.customvoice.api.speech.microsoft.com/api/texttospeech/v3.0/longaudiosynthesis/voices'
        response = requests.get(url, headers=self.header)
        print(response.text)

    def convert(self, src_txt: str) -> bool:
        if (len(str.encode(src_txt))) > 65536:
            raise ValueError("Azure engine has an implementation-imposed size limit of 65536 bytes. "
                             "Please edit the input file and try again")

        local_fn = self.app_config['output_audio_fn']
        Path(os.path.realpath(os.path.dirname(local_fn))).mkdir(parents=True, exist_ok=True)
        if os.path.exists(local_fn):
            os.remove(local_fn)

        task_cfg = speechsdk.SpeechConfig(subscription=self.api_key, region=self.region)
        audio_cfg = speechsdk.audio.AudioOutputConfig(filename=local_fn)

        # The language of the voice that speaks.
        task_cfg.speech_synthesis_voice_name = self.voice_name
        task_inst = speechsdk.SpeechSynthesizer(speech_config=task_cfg, audio_config=audio_cfg)

        # result = task_inst.speak_text_async(src_txt).get()
        esc_txt = html.escape(src_txt)
        ssml_txt = f"""<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-US">
    <voice name="{self.voice_name}">
        <prosody pitch="{self.pitch}" rate="{self.rate}">
{esc_txt}
        </prosody>
    </voice>
</speak>"""
        result = task_inst.speak_ssml_async(ssml_txt).get()
        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            return True

        err_info = result.cancellation_details
        raise RuntimeError(f"Speech synthesis FAILED. Error is:\n{err_info.error_details}")

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


if __name__ == '__main__':
    logging.basicConfig(
        format="%(asctime)s  %(levelname)s %(message)s", level=logging.INFO
    )
    inst = AzureBob(
        app_config={'azure': {}, 'output_audio_fn': '/Users/bing.wu/Downloads/azure_result.nytimes_test1.zip'})
    # inst.get_voices()
    # inst.convert_long(src_fn='/Users/bing.wu/Downloads/nytimes_test1.txt')
    # inst.wait_and_check(wait_for_sec=10, task_id='ff733b7c-f4e6-4b64-8dc6-25328a932701')
    # inst.get_synthesis()
    # inst.get_files()
#     inst.convert(src_txt="""元朝的大臣彻里帖木耳，处理公务精明干练，善于决断。
# 有一年他在浙江任职，正好逢上省城举行科举考试。他目睹了这场考试，从官府到考生都花费了许多钱财，并且免不了有营私舞弊的情况。他暗暗下了决心，待到自己掌握了大权，一定要促使朝廷废除这种制度。
# 后来，他升任相当于副宰相的中书平章政事，便奏告元顺帝，请求废除科举制度。中国科举制度隋唐以来已实行了七百多年，要废除它是一件非常重大的事，在朝中引起了巨大的反响。大师伯颜表示支持，但反对的很多。
# 有位御史坚决反对废除科举制度，他请求顺帝治彻里帖木耳的罪。不料顺帝虽然很昏庸，但对废除科举制度倒是赞成的。因此不仅不支持那位御史，反而把他贬到外地去当官。不久，他命人起草了废除科举制度的诏书，准备颁发下去。
# 书还未下达，地位略低于平章的参政许有王，又出来反对废除科举制度。他对伯颜说：“如果废除科举考试制度，世上有才能的人都会怨恨的。”
# 伯颜针锋相对地说：“如果继续实行科举考试制度，世上贪赃枉法的人还要多。”
# 许有王反驳说：“没有实行科举考试制度的时候，贪赃枉法的人也不是很多吗?”
# 伯颜讽刺他说：“我看中举的人中有用之材太少，只有你参政一个人可以任用!”
# 许有王不服气，举出许多当时中举的高官来反驳伯额。
# 伯颜当然不会改变自己的观点，于是两人争论得非常激烈。
# 第二天，满朝文武被召到祟天门听读皇帝下达的废除科举制席的诏书，许有王还特地被侮辱性地通知在班首听读。看来，皇帝特意要让这个反对者将诏书听得明白些。
# 许有王心里非常不愿意，但又惧怕得罪皇帝遭到祸害，只好勉强跪在百官前列听读诏书。听读完诏书后，百官纷纷回府，许有王满脸不高兴地低头走路。
# 有个名叫普化的御史特地走到他边上，凑着他的耳朵冷嘲热讽他说：“参政，你这下成为过河拆桥的人啦。这话的意思是，你许参政是靠科举当官的，现在宣读皇上关于废除科举制度诏书，你跪在最前面，似乎是废除科举制度的领头人，就像一个人过了桥后就把桥拆掉一样。
# 许有王听了又羞又恨，加快步伐离开。之后他借口有病，再也不上朝了
# """)
