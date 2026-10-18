"""Provider adapters; no retries, SDK defaults or inference-time teacher fallback."""
import json
import os
from urllib.request import Request,build_opener,HTTPRedirectHandler
from slm.data.schema import digest


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


class OpenAIResponses:
    identity='openai-responses-v1'
    billable=True

    def generate(self,payload):
        key=os.environ.get('OPENAI_API_KEY')
        if not key:raise RuntimeError('OPENAI_API_KEY is required for an authorized live request')
        request=Request('https://api.openai.com/v1/responses',
            data=json.dumps(payload,allow_nan=False).encode(),method='POST',
            headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
        # One HTTP attempt; transport errors remain financially uncertain in the journal.
        try:
            with build_opener(NoRedirect()).open(request,timeout=60) as response:
                data=response.read(2*1024*1024+1)
            if len(data)>2*1024*1024:raise ValueError('Provider response exceeds byte limit')
            from slm.teacher.workflow import parse_json
            return parse_json(data)
        except Exception as error:
            # Do not expose request headers, API keys or provider error-body content.
            raise RuntimeError('Teacher HTTP request failed: '+type(error).__name__) from None


class Replay:
    identity='offline-replay-v1'
    billable=False

    def __init__(self,records):
        self.records=records;self.calls=0

    def generate(self,payload):
        self.calls+=1
        result=self.records.get(digest(payload))
        if result is None:raise ValueError('No fixture matches exact request payload')
        return json.loads(json.dumps(result))
