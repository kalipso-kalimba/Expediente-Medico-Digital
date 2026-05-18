import passlib.hash as ph
h = ph.bcrypt.hash('test1234')
print('Fresh hash:', h)
print('Verify test1234:', ph.bcrypt.verify('test1234', h))
old = "\\\.YGOHsvp5kJFkvb1PCU9mp5mE7GV9Bp2"
print('Verify old hash:', ph.bcrypt.verify('test1234', old))
