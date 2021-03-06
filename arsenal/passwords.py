import keyring
from getpass import getpass

def set_password(service, user, pw=None):
    print 'Set password:'
    if pw is None:
        pw = getpass()
        print 'Type password again (for verification):'
        if pw != getpass():
            print 'Error: passwords did not match. Try again.'
            set_password(service, user)
    keyring.set_password(service, user, pw)
    return pw


def password(service, user):
    pw = keyring.get_password(service, user)
    if pw is None:
        pw = set_password(service, user)
    return pw
