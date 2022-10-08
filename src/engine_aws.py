import html
import logging
import os
import pprint
import time
from pathlib import Path
from typing import Optional

import boto3

from engine_base import VoiceEngine

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class AwsPolly(VoiceEngine):
    def __init__(self, app_config: dict):
        super().__init__(app_config, 'aws')

        call_param = {'aws_access_key_id': None, 'aws_secret_access_key': None, 'region_name': None}
        for x in call_param.keys():
            call_param[x] = self._get_key_val(x)

        session = boto3.Session(**call_param)
        self.polly_client = session.client('polly')

        self.s3_client = session.client('s3')
        self.s3_bucket = self._get_key_val('s3_bucket')
        assert self.s3_bucket, "Cannot find s3_bucket"

        self.s3_key_path = self._get_key_val('s3_key_path', self.app_config['invocation-theme-word'])

        self.lang = self._get_key_val('language_code', 'en-US')
        self.voice_id = self._get_key_val('voice_id', 'Matthew')

    def convert(self, src_txt: str) -> bool:
        logger.debug("Submitting a new async conversion task ...")
        esc_txt=html.escape(src_txt)
        ssml_txt = f"""<speak>
    <prosody rate="{self.rate}">
{esc_txt}
    </prosody>
</speak>"""
        response = self.polly_client.start_speech_synthesis_task(
            Engine='neural',
            LanguageCode=self.lang,
            OutputFormat='mp3',
            OutputS3BucketName=self.s3_bucket,
            OutputS3KeyPrefix=self.s3_key_path,
            Text=ssml_txt,
            TextType='ssml',
            VoiceId=self.voice_id,
        )

        if response['ResponseMetadata']['HTTPStatusCode'] != 200:
            raise RuntimeError("AWS call 'start_speech_synthesis_task' failed. "
                               "See response for details\n" + pprint.pformat(response, indent=2))

        task_id = response['SynthesisTask']['TaskId']
        s3_fn_loc = response['SynthesisTask']['OutputUri']
        # e.g. 'https://s3.us-west-2.amazonaws.com/web20221005-audio-files2/newyorker_test1.bec2ba2e-cce9-486c-aa8d-f84e440d28ed.mp3'

        bucket_tok = f"/{self.s3_bucket}/"
        _pos = s3_fn_loc.find(bucket_tok)
        real_s3_key = s3_fn_loc[_pos + len(bucket_tok):]
        logger.debug("Start waiting for task to complete...")
        for cnt in range(5):
            local_fn = self.wait_and_check(wait_for_sec=30, task_id=task_id, s3_path=real_s3_key)
            if local_fn:
                logger.info(f'Successfully downloaded file to {local_fn}')
                return True

        logger.info(f"""Timeout waiting for the Conversion task to complete. 
You will have to manually download the output file. Here are the artifacts:
- Task ID = {task_id}
- S3 file = {s3_fn_loc}
""")
        return False

    def wait_and_check(self, wait_for_sec: int, task_id: str, s3_path: str) -> Optional[str]:
        time.sleep(wait_for_sec)
        response = self.polly_client.get_speech_synthesis_task(TaskId=task_id)
        if response['ResponseMetadata']['HTTPStatusCode'] != 200:
            raise RuntimeError("AWS call 'get_speech_synthesis_task' failed. "
                               "See response for details\n" + pprint.pformat(response, indent=2))

        status = response['SynthesisTask']['TaskStatus']
        if status == 'failed':
            raise RuntimeError(f"SynthesisTask id={task_id} has a 'failed' status. "
                               f"You need to go to AWS Console's 'Polly S3 synthesis tasks' "
                               f"section to find out why")

        if status == 'completed':
            local_fn = self.app_config['output_audio_fn']

            Path(os.path.realpath(os.path.dirname(local_fn))).mkdir(parents=True, exist_ok=True)
            if os.path.exists(local_fn):
                os.remove(local_fn)

            self.s3_client.download_file(self.s3_bucket, s3_path, local_fn)
            if os.path.exists(local_fn):
                return local_fn
            else:
                raise RuntimeError(f"Boto3 download bucket={self.s3_bucket}, "
                                   f"path={s3_path} to {local_fn} failed to materialize?")

        return None
