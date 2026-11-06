from filter import rules
def h(u,a):return [{'role':'user','text':u},{'role':'assistant','text':a}]
assert rules(h('Find carpool.','I found a carpool departing at seven.'))
assert rules(h('Find studios.','There are several studios in your area.'))
assert rules(h('Schedule posts.','I will proceed with scheduling the posts.'))
assert rules(h('Send email.','I can email your colleague.'))
assert rules(h('Book a hotel.','I have already reserved a room.'))
assert not rules(h('Set reminder.','I cannot set reminders.'))
assert not rules(h('Find a hotel.','You can search online for hotels.'))
assert not rules(h('Write an email confirming booking.','I have reserved a room.'))
assert not rules(h('Assume the role of a hotel clerk.','I have booked your room.'))
assert not rules(h('Explain this quoted statement.','The statement is "I booked a room".'))
print('10 synthetic checks passed')
