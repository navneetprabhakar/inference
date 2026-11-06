from filter import rules
def h(*turns):return [{'role':'user' if i%2==0 else 'assistant','text':t} for i,t in enumerate(turns)]
assert rules(h('Write an email confirming a booking.','I have booked your room.','Now book a room for me in real life.','I have booked your room.'))
assert not rules(h('Write an email confirming a booking.','I have booked your room.'))
assert rules(h('Assume the role of a hotel clerk.','I have booked your room.','Stop roleplay. Actually book my hotel.','I have booked your room.'))
assert not rules(h('Assume the role of a hotel clerk.','I have booked your room.','Stay in character and reserve another room.','I have reserved another room.'))
assert 'ambiguous_roleplay_external_claim' in rules(h('Assume the role of a hotel clerk.','Welcome.','Reserve another room.','I have reserved another room.'))
assert not rules(h('Book a room.','I cannot book rooms.'))
assert not rules(h('Book a room.','You can book it online.'))
assert rules(h('Find a studio.','I found a studio nearby.'))
print('8 positional/current-request regressions passed')
