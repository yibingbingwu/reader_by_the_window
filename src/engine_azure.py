import html
import logging
import os
from pathlib import Path

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
        'chinese-广东': ('yue-CN', ['zh-HK-WanLungNeural']),
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

        all_output_formats = [m.name for m in speechsdk.SpeechSynthesisOutputFormat]
        if self.audio_format:
            assert self.audio_format in all_output_formats, (f"Current output audio format {self.audio_format} "
                                                             f"is not a valid SpeechSynthesisOutputFormat "
                                                             f"value by Azure")

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
        self.audio_format = self._get_key_val('audio_format', 'Audio24Khz48KBitRateMonoMp3')
        self.header = {
            'Ocp-Apim-Subscription-Key': self.api_key
        }
        self._resolve_locale_voice()

    def convert(self, src_txt: str) -> bool:
        if (len(str.encode(src_txt))) > 65536:
            raise ValueError("Azure engine has an implementation-imposed size limit of 65536 bytes. "
                             "Please edit the input file and try again")

        local_fn = self.app_config['output_audio_fn']
        Path(os.path.realpath(os.path.dirname(local_fn))).mkdir(parents=True, exist_ok=True)
        if os.path.exists(local_fn):
            os.remove(local_fn)

        task_cfg = speechsdk.SpeechConfig(subscription=self.api_key, region=self.region)
        task_cfg.speech_synthesis_voice_name = self.voice_name
        audio_format = speechsdk.SpeechSynthesisOutputFormat[self.audio_format]
        task_cfg.set_speech_synthesis_output_format(audio_format)

        audio_cfg = speechsdk.audio.AudioOutputConfig(filename=local_fn)

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


def eng_test_basic():
    '''
      For more samples please visit https://github.com/Azure-Samples/cognitive-services-speech-sdk
    '''

    import azure.cognitiveservices.speech as speechsdk

    # Creates an instance of a speech config with specified subscription key and service region.
    speech_key = os.getenv('SPEECH_KEY')
    service_region = "eastus"
    out_format = speechsdk.SpeechSynthesisOutputFormat.Audio24Khz48KBitRateMonoMp3
    voice_name = "en-US-JennyMultilingualNeural"

    speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=service_region)
    # Note: the voice setting will not overwrite the voice element in input SSML.
    speech_config.speech_synthesis_voice_name = voice_name
    speech_config.set_speech_synthesis_output_format(out_format)
    speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=None)

    result = speech_synthesizer.speak_text_async("I'm excited to try text to speech").get()
    stream = speechsdk.AudioDataStream(result)
    stream.save_to_wav_file("/tmp/engine_azure.mp3")
    print('Output file generated')


def get_voices(region: str, api_key: str):
    # Display as plain text what the Voice Names are available for the Speech Resource represented by this key
    url = f'https://{region}.customvoice.api.speech.microsoft.com/api/texttospeech/v3.0/longaudiosynthesis/voices'
    response = requests.get(url, headers={'Ocp-Apim-Subscription-Key': api_key})
    print(response.text)


if __name__ == '__main__':
    eng_test_basic()
# get_voices(region=os.getenv('SPEECH_REGION'), api_key=os.getenv('SPEECH_KEY'))
