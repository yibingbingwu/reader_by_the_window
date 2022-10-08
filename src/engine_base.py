import os
from abc import ABC, abstractmethod


class VoiceEngine(object):
    def __init__(self, app_config: dict, eng: str):
        self.app_config = app_config
        self.eng = eng
        self._calc_tone_change()

    def _get_key_val(self, key: str, def_val: str = None) -> str:
        val = self.app_config[self.eng].get(key, None) or os.getenv(key.upper(), None) or def_val
        assert val, f"Missing key/value for '{key}'"
        return val or def_val

    def _calc_tone_change(self):
        if self.app_config[self.eng].get('speed'):
            self.rate = '{:d}%'.format(int(float(self.app_config[self.eng]['speed']) * 100))
        else:
            self.rate = "100%"

        if self.app_config[self.eng].get('pitch'):
            self.pitch = '{:d}%'.format(int(float(self.app_config[self.eng]['pitch']) * 100))
        else:
            self.pitch = "100%"

    @abstractmethod
    def convert(self, src_txt: str) -> bool:
        pass
