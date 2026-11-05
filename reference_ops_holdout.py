"""Fresh mixed utterances evaluated before optional promotion. Includes unsupported forms."""
POSITIVE = [
 ('Please add nineteen to the last result.', 'add', 19),
 ('Now increase the returned answer by four.', 'add', 4),
 ('Could you sum my previous total and eight?', 'add', 8),
 ('Then multiply that number by 2.', 'multiply', 2),
 ('Scale the recorded answer by three, please.', 'multiply', 3),
 ('Take six times the previous output.', 'multiply', 6),
 ('Please subtract two from that answer.', 'subtract', 2),
 ('Decrease the observed result by five.', 'subtract', 5),
 ('Take four away from my previous total.', 'subtract', 4),
 ('Now subtract the latest answer from twenty.', 'reverse_subtract', 20),
 ('Thirty minus the prior number, please.', 'reverse_subtract', 30),
 ('Take the returned number away from nine.', 'reverse_subtract', 9),
 ('Next divide the latest total by three.', 'divide', 3),
 ('The returned value divided by four, please.', 'divide', 4),
 ('What is the quotient of the last result and seven?', 'divide', 7),
 ('Now divide ten by the returned total.', 'reverse_divide', 10),
 ('Forty divided by the latest result, please.', 'reverse_divide', 40),
 ('How many times does the last value fit into seven?', 'reverse_divide', 7)
]
NEGATIVE = [
 'What number did the last tool return?', 'Was the previous result smaller than seven?',
 'How much did I ask you to subtract from it?', 'Could we have multiplied that number by three?',
 'Describe how to add four to that answer.', 'Do not divide the previous total by two.',
 'If I subtract the last result from seven, what would happen?', 'Quote “add 9 to the last answer”.',
 'What is an output?', 'Add two and five.', 'Which tool computed the total?',
 'Convert that value to meters.', 'Add four to that number and double it.',
 'Please add two to the answer from the first call.', 'Add 1/3 to the last value.',
 'Divide it by 3e5.', 'Subtract two dollars from my prior total.', 'Add 4 percent to it.'
]
