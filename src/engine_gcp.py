# NOT active
# Run: GOOGLE_APPLICATION_CREDENTIALS=/Users/bing.wu/.ssh/personal_gcp_svc_acct.json gcloud auth application-default print-access-token | pbcopy
import base64
import logging

import requests

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

TEST_SIG = "ya29.c.b0AUFJQsFQ9y25m6MpXmzDH2Vj1MalANmwhpv7Yy50sYzSXUS3jqngcYqvO1Vzbui3cVZfO8kLLvgU_GC81Qu5RgsKP8aDpemCtg9fUc6Mk3p9N-sziXiix1zLl5cFxESQttBGYgGip1-dg4a0N0OPkJh2ANpseAvhAFSIRYIWJBYhuF73JYI8hIsWVqx91xruILjPjKN2BZK7PYv7m9ZWr_Zak0KSRc4........................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................................"
GCP_T2S_HEADER = {
    "Content-Type": "application/json; charset=utf-8",
    "Authorization": 'Bearer ' + TEST_SIG,
}


def gcp_text2speech(src_txt: str, out_fn: str) -> Any:
    payload = {
        "audioConfig": {
            "audioEncoding": "LINEAR16",
            "pitch": 0,
            "speakingRate": 0.94
        },
        "input": {
            "text": src_txt[:5000]
        },
        "voice": {
            # "languageCode": "en-US",
            "languageCode": "zh-guoyu",
            "name": "en-US-Wavenet-D",
            # "name": "en-US-Neural2-F",
        }
    }
    resp = requests.post(url='https://texttospeech.googleapis.com/v1/text:synthesize',
                         json=payload,
                         headers=GCP_T2S_HEADER
                         )
    if resp.status_code != 200:
        err_dict = resp.json().get('error', {})
        msg = (
            f"Remote GCP synthesize call failed. The error is '{err_dict['code']}', "
            f"message is '{err_dict['message']}'"
        )
        logger.error(msg)
        raise RuntimeError(msg)

    ret_data = resp.json()["audioContent"]
    with open(out_fn, 'wb') as fout:
        fout.write(bytearray(base64.b64decode(ret_data)))

    return True
