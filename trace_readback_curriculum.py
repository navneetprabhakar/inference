"""Independent intent teaching for latest-event questions. No stored conversation imports."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIR = ROOT / 'reports/trace-readback'
# Each phrase is a complete utterance. Surface variants do not constitute independent tests.
PHRASES = {
 'result': 'what result did the tool return|repeat the last result|what was the output|tell me the final number again|what answer came back from that call|give me the value it returned|what did the calculation produce|read back the converted result',
 'a': 'what was operand a|what was the first operand|which number came first in the calculation|repeat the left operand|what was the first input to the calculator|what number was in the left slot',
 'b': 'what was operand b|what was the second operand|which number came second in the calculation|repeat the right operand|what was the second input to the calculator|what number was in the right slot',
 'amount': 'what amount did we convert|what was the input amount|which quantity went into the converter|what was the original quantity|what input value was converted|how much did we start with before conversion',
 'source': 'what was the source unit|which unit did we convert from|what units did we start with|which unit was the input in|what was the original unit of measure|repeat the starting unit',
 'target': 'what was the target unit|which unit did we convert to|what units did we end with|which unit was the output in|what was the destination unit of measure|repeat the ending unit',
 'tool': 'which tool ran last|what tool was called|name the last tool|which adapter ran on my last request|what was the last tool name|which tool handled that operation',
 'status': 'did the last call fail|what error did the tool report|did the tool succeed|what happened to the last call|why did the last call fail|did that call produce a result|was there an error last time',
 'positive': 'was the last result positive|was the output greater than zero|did the number come out positive|was the result above zero',
 'negative': 'was the last result negative|was the output less than zero|did the number come out negative|was the result below zero',
 'zero': 'was the last result zero|did the output equal zero|was the returned number exactly zero',
 'gt': 'was the result greater than 15|was the output above 2|did the returned number exceed -3|was the answer more than 6',
 'lt': 'was the result less than 15|was the output below 2|was the returned number under -3|was the answer smaller than 6',
 'eq': 'was the result equal to 15|was the output exactly 2|did the answer equal -3|was the last result 6',
 'defer': 'what is a tool|what is a positive number|what are the browser developer tools|which unit did the army belong to|who was the first person there|what was the second chapter about|what is the target audience|read the last sentence|what happened to the character|why did the project fail|what is my name|what is your favorite tool|is 9 greater than 2|what does operand mean|give me a positive adjective|tell me the final score in the game|calculate 15 plus 3|convert 4 inches to feet|please double the last result|subtract 5 from the returned number|convert the output to meters|multiply the second operand by 4|repeat the calculation with 8|add 2 to the original quantity|use the result as input for another calculation|what will the next result be|what was the result of the match|was the last result greater than the first result|what would the result have been if it were negative|was the output above or equal to 3|give me the first and second operands|what was positive about the result|what was the unit price|which tool should I use|do not repeat the last output',
}


def generated():
    for label, block in PHRASES.items():
        for phrase in block.split('|'):
            for prefix, suffix in [('', '?'), ('Please tell me, ', '.'), ('One more thing — ', '?')]:
                yield dict(user=prefix+phrase+suffix, label=label)


if __name__ == '__main__':
    DIR.mkdir(exist_ok=True, parents=True)
    (DIR/'candidate-teaching.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in generated()))
