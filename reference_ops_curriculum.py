"""Independently authored reference-operation teaching, normalized by the trainable router."""
import json
from pathlib import Path

DIR = Path(__file__).resolve().parent/'reports/reference-ops'
EXAMPLES = {
    'add': 'add 13 to the prior output|increase that value by 4|the previous result plus 7|add the last answer and 3|add 5 to it',
    'multiply': 'multiply the prior output by 13|scale the last answer by 4|the previous result times 7|multiply 3 by that value',
    'subtract': 'subtract 13 from the prior output|reduce that value by 4|the previous result minus 7|decrease the last answer by 3',
    'reverse_subtract': 'subtract the prior output from 13|4 minus the previous result|subtract it from 7',
    'divide': 'divide the prior output by 13|the last answer divided by 4|divide it by 7',
    'reverse_divide': 'divide 13 by the prior output|4 divided by the previous result|divide 7 by it',
    'defer': 'what was the prior output|was the last answer above 13|what did we add to the last answer|what is an output|add 5 and 9|why did you divide the last result by 7|can you define multiply|what was the value before we added 3|what was the second input|was the result positive|do not add 3 to it|what if we divide it by 8'
}


def rows():
    for label, block in EXAMPLES.items():
        for user in block.split('|'):
            yield {'user':user,'label':label}


if __name__=='__main__':
    (DIR/'candidate-teaching.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows()))
